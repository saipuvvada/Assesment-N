import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.goal import Plan, Goal
from ott_agent.models.decision import Decision, Action, Outcome
from ott_agent.models.event import Event
from ott_agent.models.viewer import ViewerState
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.evidence_service import EvidenceService

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


UNAVAILABLE_SIGNALS = {"churn_risk_score", "user_cancellation_intent_event"}


class OutcomeEvaluatorService:
    """Dedicated outcome evaluation engine for assessing goal success/failure and closing the agent loop."""

    def __init__(self, db: Session):
        self.db = db
        self.viewer_service = ViewerService(db)
        self.evidence_service = EvidenceService(db)

    def evaluate_active_plans(self, evaluation_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Evaluate all active decisions and plans against event stream and deadlines."""
        now = ensure_utc(evaluation_time or utc_now())
        results = []

        stmt = select(Decision).where(Decision.status == "ACTIVE")
        active_decisions = list(self.db.execute(stmt).scalars().all())

        for decision in active_decisions:
            res = self.evaluate_single_decision(decision.id, now)
            results.append(res)

        return results

    def evaluate_single_decision(self, decision_id: str, evaluation_time: Optional[datetime] = None) -> Dict[str, Any]:
        now = ensure_utc(evaluation_time or utc_now())
        stmt = select(Decision).where(Decision.id == decision_id)
        decision = self.db.execute(stmt).scalar_one_or_none()

        if not decision:
            return {"decision_id": decision_id, "status": "UNKNOWN", "reason": "Decision not found"}

        success_signal = decision.success_signal or "watch_complete"

        # Signal check: If success signal is unavailable in stream -> INCONCLUSIVE
        if success_signal in UNAVAILABLE_SIGNALS:
            return self._record_outcome(decision, "INCONCLUSIVE", 0.0, "Success signal unavailable in stream")

        deadline_t = ensure_utc(decision.deadline_timestamp) if decision.deadline_timestamp else (decision.created_at + timedelta(days=1))
        content_refs = json.loads(decision.content_references_json) if decision.content_references_json else []
        target_content_id = content_refs[0] if content_refs else None

        # Search for qualifying success events
        stmt_ev = (
            select(Event)
            .where(
                Event.viewer_id == decision.viewer_id,
                Event.event_timestamp >= ensure_utc(decision.created_at),
                Event.event_timestamp <= deadline_t
            )
            .order_by(Event.event_timestamp.asc())
        )
        events = list(self.db.execute(stmt_ev).scalars().all())

        qualifying_event = None
        for ev in events:
            if ev.event_type in ("watch_complete", "watch_start", "rating"):
                payload = json.loads(ev.payload_json) if ev.payload_json else {}
                c_id = payload.get("content_id") or ev.event_id
                if not target_content_id or c_id == target_content_id or target_content_id in str(payload):
                    qualifying_event = ev
                    break

        if qualifying_event:
            # Goal SUCCEEDED!
            res = self._record_outcome(
                decision,
                "SUCCEEDED",
                1.0,
                f"Qualifying event '{qualifying_event.event_type}' (id: {qualifying_event.event_id}) observed at {qualifying_event.event_timestamp.isoformat()}.",
                evidence_event_id=qualifying_event.event_id or qualifying_event.id
            )
            self._close_plan(decision.plan_id, "COMPLETED")
            return res

        # Check if deadline passed
        if now > deadline_t:
            # Deadline passed without qualifying event -> FAILED
            res = self._record_outcome(
                decision,
                "FAILED",
                0.0,
                f"Deadline ({deadline_t.isoformat()}) passed without observing qualifying success signal '{success_signal}'."
            )
            self._close_plan(decision.plan_id, "CANCELLED")
            return res

        # Otherwise still PENDING
        return {
            "decision_id": decision.id,
            "status": "PENDING",
            "reason": f"Active decision pending deadline at {deadline_t.isoformat()}"
        }

    def _record_outcome(
        self,
        decision: Decision,
        status: str,
        value: float,
        reason: str,
        evidence_event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        decision.status = status
        self.db.commit()

        action = self.db.execute(select(Action).where(Action.decision_id == decision.id)).scalar_one_or_none()

        outcome = Outcome(
            action_id=action.id if action else None,
            viewer_id=decision.viewer_id,
            metric_name=f"goal_success:{decision.goal_id or 'general'}",
            metric_value=value,
            outcome_timestamp=utc_now(),
            metadata_json=json.dumps({
                "status": status,
                "reason": reason,
                "evidence_event_id": evidence_event_id,
                "decision_id": decision.id
            })
        )
        self.db.add(outcome)
        self.db.commit()
        self.db.refresh(outcome)

        # Record learned fact in viewer history
        self.evidence_service.record_fact(
            viewer_internal_id=decision.viewer_id,
            fact_type="learned_outcome",
            fact_key=f"outcome:{decision.goal_id or 'general'}",
            fact_value=status,
            source_type="outcome_evaluator",
            source_record_id=outcome.id,
            evidence_event_id=evidence_event_id
        )

        return {
            "outcome_id": outcome.id,
            "decision_id": decision.id,
            "status": status,
            "value": value,
            "reason": reason
        }

    def _close_plan(self, plan_id: Optional[str], new_status: str):
        if not plan_id:
            return
        plan = self.db.execute(select(Plan).where(Plan.id == plan_id)).scalar_one_or_none()
        if plan and plan.plan_status == "ACTIVE":
            plan.plan_status = new_status
            plan.deactivated_at = utc_now()
            self.db.commit()
