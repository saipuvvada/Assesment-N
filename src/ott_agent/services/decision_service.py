import json
import logging
from typing import Optional, List, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.decision import Decision, Action, Outcome

logger = logging.getLogger(__name__)


class DecisionService:
    def __init__(self, db: Session):
        self.db = db

    def record_decision(
        self,
        viewer_internal_id: str,
        decision_type: str,
        recommended_action: str,
        rationale: str,
        evidence_refs: List[Any],
        plan_id: Optional[str] = None
    ) -> Decision:
        """Store an agent decision with explicit evidence references."""
        decision = Decision(
            viewer_id=viewer_internal_id,
            plan_id=plan_id,
            decision_type=decision_type,
            recommended_action=recommended_action,
            rationale=rationale,
            evidence_refs_json=json.dumps(evidence_refs)
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return decision

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Fetch decision by ID."""
        stmt = select(Decision).where(Decision.id == decision_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_decisions_for_viewer(self, viewer_internal_id: str) -> List[Decision]:
        """Fetch all decisions recorded for a viewer."""
        stmt = (
            select(Decision)
            .where(Decision.viewer_id == viewer_internal_id)
            .order_by(Decision.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def record_action(
        self,
        decision_id: str,
        viewer_internal_id: str,
        action_type: str,
        payload: Dict[str, Any],
        status: str = "EXECUTED",
        verification_result: Optional[Dict[str, Any]] = None
    ) -> Action:
        """Record an executed action for a decision."""
        action = Action(
            decision_id=decision_id,
            viewer_id=viewer_internal_id,
            action_type=action_type,
            payload_json=json.dumps(payload),
            status=status,
            verification_result_json=json.dumps(verification_result) if verification_result else None
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action

    def record_outcome(
        self,
        viewer_internal_id: str,
        metric_name: str,
        metric_value: float,
        action_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Outcome:
        """Record an observed outcome."""
        outcome = Outcome(
            action_id=action_id,
            viewer_id=viewer_internal_id,
            metric_name=metric_name,
            metric_value=metric_value,
            metadata_json=json.dumps(metadata) if metadata else None
        )
        self.db.add(outcome)
        self.db.commit()
        self.db.refresh(outcome)
        return outcome
