import time
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.viewer import Viewer, ViewerState
from ott_agent.models.decision import Decision, Action
from ott_agent.models.catalogue import ContentItem
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.evidence_service import EvidenceService
from ott_agent.services.planner_service import PlannerService
from ott_agent.services.verification_service import VerificationService
from ott_agent.services.content_selection_service import ContentSelectionService
from ott_agent.services.messaging_service import MessagingControlService
from ott_agent.services.executor_service import MockActionExecutorService
from ott_agent.services.circuit_breaker import CircuitBreaker, log_latency_measurement, log_processing_error
from ott_agent.providers.mock_provider import RuleBasedModelProvider
from ott_agent.providers.base import ProviderBudgetConfig

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


class ViewerAgentService:
    """Per-Viewer Agent owning facts, goal selection, plan reuse/replanning, decision generation, and independent verification."""

    def __init__(self, db: Session, model_provider=None):
        self.db = db
        self.viewer_service = ViewerService(db)
        self.evidence_service = EvidenceService(db)
        self.planner_service = PlannerService(db)
        self.verifier = VerificationService(db)
        self.content_service = ContentSelectionService(db)
        self.messaging_service = MessagingControlService(db)
        self.executor = MockActionExecutorService(db)
        self.circuit_breaker = CircuitBreaker()
        self.provider = model_provider or RuleBasedModelProvider()

    def process_app_open_trigger(
        self,
        viewer_id: str,
        trigger_event_id: Optional[str] = None,
        trigger_timestamp: Optional[datetime] = None,
        intervention_override_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process app-open trigger for a viewer, enforce verification & call budgets, and execute action."""
        start_mono = time.monotonic()
        now = utc_now()
        trig_time = trigger_timestamp or now
        if trig_time.tzinfo is None:
            trig_time = trig_time.replace(tzinfo=timezone.utc)
        event_age_sec = max(0.0, (now - trig_time).total_seconds())

        # 1. Fetch or create viewer
        viewer = self.viewer_service.get_by_viewer_id(viewer_id)
        if not viewer:
            viewer = self.viewer_service.create_or_update_viewer(viewer_id=viewer_id)

        latest_state = self.viewer_service.get_latest_state(viewer.id)

        # 2. Resolve evidence facts & precedence
        eff_dialect, dialect_src, has_dialect_conflict, dialect_history = (
            self.evidence_service.resolve_effective_fact(viewer.id, "dialect_preference")
        )
        selected_dialect = eff_dialect or (latest_state.dialect_preference if latest_state else "Egyptian Arabic")
        selected_dialect_src = dialect_src or "profile"

        eff_sub, sub_src, has_sub_conflict, _ = (
            self.evidence_service.resolve_effective_fact(viewer.id, "subscription_status")
        )

        # 3. Plan reuse or purchase-triggered replanning
        plan, goal_eval, is_reused, plan_rationale = self.planner_service.get_or_create_plan(
            viewer_internal_id=viewer.id,
            viewer_state=latest_state,
            trigger_type="app_open"
        )

        # Build catalogue list
        catalogue_items = self.db.execute(select(ContentItem)).scalars().all()
        cat_dicts = []
        for c in catalogue_items:
            # Prompt injection defense check: skip malicious catalogue items
            if self.content_service.is_text_prompt_injection(c.title) or self.content_service.is_text_prompt_injection(str(c.metadata_json or "")):
                continue
            cat_dicts.append({"content_id": c.content_id, "title": c.title, "dialect": c.dialect, "availability_start": c.availability_start.isoformat(), "availability_end": c.availability_end.isoformat()})

        state_dict = {
            "dialect_preference": selected_dialect,
            "language_variant": latest_state.language_variant if latest_state else "ar-EG",
            "engagement_score": latest_state.engagement_score if latest_state else 0.5,
            "subscription_status": eff_sub or (latest_state.subscription_status if latest_state else "FREE")
        }

        passed_checks = []
        failed_checks = []
        assumptions = []
        conflicts = []

        if has_dialect_conflict:
            conflicts.append("Conflicting dialect evidence detected across settings and past events.")

        if has_sub_conflict:
            conflicts.append("Conflicting subscription evidence detected between profile and purchase events.")

        # If no plan or goal is eligible -> ABSTAIN
        if not plan or not goal_eval:
            passed_checks.append("Viewer profile retrieved successfully")
            failed_checks.append("No eligible goal found")
            latency_ms = (time.monotonic() - start_mono) * 1000.0
            log_latency_measurement(self.db, "process_app_open_trigger_abstain", latency_ms)

            decision = Decision(
                viewer_id=viewer.id,
                plan_id=None,
                trigger_type="app_open",
                trigger_event_id=trigger_event_id,
                trigger_event_age_seconds=event_age_sec,
                goal_id=None,
                rule_version=1,
                decision_type="NO_ACTION",
                recommended_action="ABSTAIN",
                selected_dialect=selected_dialect,
                dialect_source=selected_dialect_src,
                content_references_json="[]",
                confidence_score=1.0,
                rationale=plan_rationale,
                evidence_refs_json=json.dumps(dialect_history),
                evidence_freshness_json=json.dumps({"event_age_seconds": event_age_sec}),
                assumptions_json=json.dumps(assumptions),
                conflicts_json=json.dumps(conflicts),
                passed_checks_json=json.dumps(passed_checks),
                failed_checks_json=json.dumps(failed_checks),
                decision_latency_ms=latency_ms,
                status="ABSTAINED",
                abstention_reason=plan_rationale
            )
            self.db.add(decision)
            self.db.commit()
            self.db.refresh(decision)
            return self._build_audit_payload(decision, viewer_id)

        passed_checks.append("Eligible goal selected")
        passed_checks.append("Single active plan invariant satisfied")
        assumptions.append(f"Viewer will respond to content in dialect '{selected_dialect}'")

        # 4. Model provider invocation protected by CircuitBreaker
        goal_rules_data = [{"goal_code": goal_eval.goal_code, "version": goal_eval.version}]
        try:
            provider_res, _ = self.circuit_breaker.execute(
                self.provider.generate_decision,
                viewer_id=viewer_id,
                viewer_state=state_dict,
                available_catalogue=cat_dicts,
                goal_rules=goal_rules_data
            )
        except Exception as e:
            logger.warning(f"Circuit breaker / provider error: {e}. Using deterministic fallback.")
            log_processing_error(self.db, "provider_circuit_breaker", e)
            provider_res = self.provider._fallback_decision(state_dict, cat_dicts, str(e))

        target_action_type = intervention_override_type or "HOMEPAGE_ROW"
        rec_action = provider_res.get("recommended_action", "RECOMMEND_SHOW:show_201")
        content_ref = rec_action.split(":")[-1] if ":" in rec_action else "show_201"

        # Construct stable idempotency key for action
        idempotency_key = f"{viewer_id}:{trigger_event_id or 'app_open'}:{goal_eval.goal_id}:{target_action_type}"

        # Check if action with idempotency_key already exists in DB
        existing_action = self.db.execute(
            select(Action).where(Action.idempotency_key == idempotency_key)
        ).scalar_one_or_none()

        latency_ms = (time.monotonic() - start_mono) * 1000.0
        log_latency_measurement(self.db, "process_app_open_trigger_active", latency_ms)

        decision = Decision(
            viewer_id=viewer.id,
            plan_id=plan.id,
            trigger_type="app_open",
            trigger_event_id=trigger_event_id,
            trigger_event_age_seconds=event_age_sec,
            goal_id=goal_eval.goal_id,
            rule_version=goal_eval.version,
            deadline_timestamp=goal_eval.deadline_timestamp,
            success_signal=goal_eval.success_signal,
            decision_type=target_action_type,
            recommended_action=rec_action,
            selected_dialect=selected_dialect,
            dialect_source=selected_dialect_src,
            content_references_json=json.dumps([content_ref]),
            confidence_score=0.9,
            rationale=f"{plan_rationale} {provider_res.get('rationale', '')}",
            evidence_refs_json=json.dumps(goal_eval.eligibility_evidence + [f"dialect_src:{selected_dialect_src}"]),
            evidence_freshness_json=json.dumps({"trigger_age_seconds": event_age_sec}),
            assumptions_json=json.dumps(assumptions),
            conflicts_json=json.dumps(conflicts),
            passed_checks_json=json.dumps(passed_checks),
            failed_checks_json=json.dumps(failed_checks),
            decision_latency_ms=latency_ms,
            status="ACTIVE"
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)

        # If action idempotency key already exists, return audit payload without inserting duplicate Action row
        if existing_action:
            decision.status = "REJECTED"
            decision.abstention_reason = f"Duplicate action trigger detected with idempotency_key '{idempotency_key}'."
            self.db.commit()
            return self._build_audit_payload(decision, viewer_id)

        # 5. Perform Independent Action Verification (100% separate from provider/planner)
        is_verified, verification_reasons = self.verifier.verify_action(
            decision_id=decision.id,
            action_type=target_action_type,
            proposed_payload={"content_id": content_ref, "dialect": selected_dialect},
            idempotency_key=idempotency_key,
            execution_time=now
        )

        # 6. Create Action and Execute via Mock Action Executor
        action = Action(
            decision_id=decision.id,
            viewer_id=viewer.id,
            idempotency_key=idempotency_key,
            action_type=target_action_type,
            payload_json=json.dumps({"content_id": content_ref, "dialect": selected_dialect}),
            verification_status="VERIFIED" if is_verified else "REJECTED",
            verification_failed_reasons_json=json.dumps(verification_reasons),
            status="PENDING"
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)

        exec_status, exec_result = self.executor.execute_action(
            action_id=action.id,
            is_verified=is_verified,
            verification_failed_reasons=verification_reasons
        )

        if not is_verified:
            decision.status = "REJECTED"
            decision.abstention_reason = f"Verification rejected action: {'; '.join(verification_reasons)}"
            self.db.commit()

        return self._build_audit_payload(decision, viewer_id)

    def _build_audit_payload(self, decision: Decision, viewer_external_id: str) -> Dict[str, Any]:
        """Format machine-readable decision audit JSON structure."""
        return {
            "decision_id": decision.id,
            "viewer_id": viewer_external_id,
            "trigger_details": {
                "trigger_type": decision.trigger_type,
                "trigger_event_id": decision.trigger_event_id,
                "trigger_event_age_seconds": decision.trigger_event_age_seconds
            },
            "goal_details": {
                "goal_id": decision.goal_id,
                "rule_version": decision.rule_version,
                "deadline_timestamp": decision.deadline_timestamp.isoformat() if decision.deadline_timestamp else None,
                "success_signal": decision.success_signal
            },
            "proposed_action": decision.recommended_action,
            "dialect_selection": {
                "selected_dialect": decision.selected_dialect,
                "source": decision.dialect_source
            },
            "content_references": json.loads(decision.content_references_json) if decision.content_references_json else [],
            "confidence_and_rationale": {
                "confidence_score": decision.confidence_score,
                "rationale": decision.rationale
            },
            "evidence": {
                "evidence_references": json.loads(decision.evidence_refs_json) if decision.evidence_refs_json else [],
                "freshness": json.loads(decision.evidence_freshness_json) if decision.evidence_freshness_json else {}
            },
            "assumptions": json.loads(decision.assumptions_json) if decision.assumptions_json else [],
            "conflicts": json.loads(decision.conflicts_json) if decision.conflicts_json else [],
            "checks": {
                "passed_checks": json.loads(decision.passed_checks_json) if decision.passed_checks_json else [],
                "failed_checks": json.loads(decision.failed_checks_json) if decision.failed_checks_json else []
            },
            "decision_latency_ms": decision.decision_latency_ms,
            "status": decision.status,
            "abstention_reason": decision.abstention_reason,
            "created_at": decision.created_at.isoformat()
        }
