import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.viewer import ViewerFact, ViewerState, Viewer

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


SOURCE_PRECEDENCE = {
    "dialect_preference": {
        "app_settings": 100,
        "subtitle_change": 80,
        "watch_start": 60,
        "profile": 40,
        "default": 10
    },
    "subscription_status": {
        "purchase_event": 100,
        "subscription_start": 90,
        "profile": 30,
        "default": 10
    }
}


class EvidenceService:
    def __init__(self, db: Session):
        self.db = db

    def record_fact(
        self,
        viewer_internal_id: str,
        fact_type: str,
        fact_key: str,
        fact_value: str,
        source_type: str,
        source_record_id: Optional[str] = None,
        observation_time: Optional[datetime] = None,
        confidence: float = 1.0,
        evidence_event_id: Optional[str] = None
    ) -> ViewerFact:
        """Record an evidence-backed fact and evaluate conflict resolution rules."""
        obs_time = ensure_utc(observation_time or utc_now())
        rec_time = utc_now()

        # Check existing facts for key
        stmt = (
            select(ViewerFact)
            .where(
                ViewerFact.viewer_id == viewer_internal_id,
                ViewerFact.fact_key == fact_key
            )
            .order_by(ViewerFact.created_at.desc())
        )
        existing_facts = list(self.db.execute(stmt).scalars().all())

        has_conflict = False
        conflict_details = None
        rule_applied = None
        reason_applied = None

        if existing_facts:
            latest = existing_facts[0]
            latest_obs = ensure_utc(latest.observation_time)
            # Check if values conflict
            if latest.fact_value != str(fact_value):
                # Precedence evaluation
                prec_map = SOURCE_PRECEDENCE.get(fact_key, {})
                new_prec = prec_map.get(source_type, 20)
                old_prec = prec_map.get(latest.source_type, 20)

                # Late event check: if incoming observation is older than latest observation
                if obs_time < latest_obs:
                    has_conflict = True
                    rule_applied = "LATE_EVENT_STALE_RULE"
                    reason_applied = (
                        f"Incoming fact from '{source_type}' (time {obs_time.isoformat()}) is older "
                        f"than existing fact from '{latest.source_type}' (time {latest_obs.isoformat()}). "
                        "Retaining existing fact."
                    )
                    conflict_details = json.dumps({
                        "existing_value": latest.fact_value,
                        "incoming_value": str(fact_value),
                        "conflict_reason": "Out-of-order late event"
                    })
                elif new_prec > old_prec:
                    rule_applied = f"SOURCE_PRECEDENCE_{source_type.upper()}"
                    reason_applied = (
                        f"Incoming source '{source_type}' (precedence {new_prec}) overrides "
                        f"existing source '{latest.source_type}' (precedence {old_prec})."
                    )
                elif new_prec < old_prec:
                    rule_applied = f"SOURCE_PRECEDENCE_{latest.source_type.upper()}"
                    reason_applied = (
                        f"Existing source '{latest.source_type}' (precedence {old_prec}) overrides "
                        f"incoming source '{source_type}' (precedence {new_prec})."
                    )
                else:
                    # Equal precedence with different values -> Unresolved conflict
                    has_conflict = True
                    rule_applied = "UNRESOLVED_CONFLICT_PRESERVED"
                    reason_applied = (
                        f"Conflicting values '{latest.fact_value}' vs '{fact_value}' from sources of equal "
                        f"precedence ({source_type}). Preserving conflict state for audit."
                    )
                    conflict_details = json.dumps({
                        "existing_value": latest.fact_value,
                        "incoming_value": str(fact_value),
                        "conflict_reason": "Equal precedence disagreement"
                    })

        fact = ViewerFact(
            viewer_id=viewer_internal_id,
            fact_type=fact_type,
            fact_key=fact_key,
            fact_value=str(fact_value),
            evidence_event_id=evidence_event_id or source_record_id,
            source_type=source_type,
            source_record_id=source_record_id,
            observation_time=obs_time,
            received_time=rec_time,
            confidence=confidence,
            has_conflict=has_conflict,
            conflict_details_json=conflict_details,
            resolution_rule=rule_applied,
            resolution_reason=reason_applied
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)

        # Update viewer state summary
        self._update_viewer_state_summary(viewer_internal_id, fact_key, str(fact_value), source_type, rule_applied)
        return fact

    def resolve_effective_fact(self, viewer_internal_id: str, fact_key: str) -> Tuple[Optional[str], Optional[str], bool, List[Dict[str, Any]]]:
        """Resolve effective value, source, conflict status, and history for a fact key."""
        stmt = (
            select(ViewerFact)
            .where(
                ViewerFact.viewer_id == viewer_internal_id,
                ViewerFact.fact_key == fact_key
            )
            .order_by(ViewerFact.observation_time.desc())
        )
        facts = list(self.db.execute(stmt).scalars().all())

        if not facts:
            return None, None, False, []

        prec_map = SOURCE_PRECEDENCE.get(fact_key, {})
        # Sort by precedence descending, then observation_time descending
        sorted_facts = sorted(
            facts,
            key=lambda f: (prec_map.get(f.source_type, 20), ensure_utc(f.observation_time).timestamp()),
            reverse=True
        )

        effective_fact = sorted_facts[0]
        has_conflict = any(f.has_conflict for f in facts)

        history = []
        now = utc_now()
        for f in facts:
            f_obs = ensure_utc(f.observation_time)
            age_sec = (now - f_obs).total_seconds()
            history.append({
                "id": f.id,
                "value": f.fact_value,
                "source_type": f.source_type,
                "source_record_id": f.source_record_id,
                "observation_time": f_obs.isoformat(),
                "age_seconds": round(age_sec, 1),
                "confidence": f.confidence,
                "has_conflict": f.has_conflict,
                "resolution_rule": f.resolution_rule,
                "resolution_reason": f.resolution_reason
            })

        return effective_fact.fact_value, effective_fact.source_type, has_conflict, history

    def _update_viewer_state_summary(
        self,
        viewer_internal_id: str,
        fact_key: str,
        fact_value: str,
        source_type: str,
        rule_applied: Optional[str]
    ):
        stmt = (
            select(ViewerState)
            .where(ViewerState.viewer_id == viewer_internal_id)
            .order_by(ViewerState.updated_at.desc())
            .limit(1)
        )
        state = self.db.execute(stmt).scalar_one_or_none()

        if not state:
            state = ViewerState(
                viewer_id=viewer_internal_id,
                dialect_preference="Egyptian Arabic",
                language_variant="ar-EG",
                engagement_score=0.5,
                subscription_status="FREE"
            )
            self.db.add(state)
            self.db.flush()

        eff_val, eff_src, _, _ = self.resolve_effective_fact(viewer_internal_id, fact_key)
        final_val = eff_val or fact_value

        if fact_key == "dialect_preference":
            state.dialect_preference = final_val
        elif fact_key == "subscription_status":
            state.subscription_status = final_val

        self.db.commit()
