import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from ott_agent.models.goal import Plan, Goal

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


class PlanService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_plan(self, viewer_internal_id: str) -> Optional[Plan]:
        """Fetch the active plan for a viewer."""
        stmt = (
            select(Plan)
            .where(Plan.viewer_id == viewer_internal_id, Plan.plan_status == "ACTIVE")
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_plan(
        self,
        viewer_internal_id: str,
        goal_id: str,
        steps: List[Any],
        replace_existing: bool = True
    ) -> Plan:
        """Create a new plan for a viewer, enforcing single active plan invariant."""
        active_plan = self.get_active_plan(viewer_internal_id)
        if active_plan:
            if replace_existing:
                active_plan.plan_status = "CANCELLED"
                active_plan.deactivated_at = utc_now()
                self.db.flush()
            else:
                raise ValueError(f"Viewer {viewer_internal_id} already has an active plan: {active_plan.id}")

        plan = Plan(
            viewer_id=viewer_internal_id,
            goal_id=goal_id,
            plan_status="ACTIVE",
            steps_json=json.dumps(steps)
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def complete_plan(self, plan_id: str) -> Optional[Plan]:
        """Mark a plan as COMPLETED."""
        stmt = select(Plan).where(Plan.id == plan_id)
        plan = self.db.execute(stmt).scalar_one_or_none()
        if plan and plan.plan_status == "ACTIVE":
            plan.plan_status = "COMPLETED"
            plan.deactivated_at = utc_now()
            self.db.commit()
            self.db.refresh(plan)
        return plan
