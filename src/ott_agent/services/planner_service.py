import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.goal import Plan, Goal
from ott_agent.models.viewer import ViewerState
from ott_agent.services.plan_service import PlanService
from ott_agent.services.goal_evaluator import GoalEvaluatorService, GoalEvaluationResult

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


class PlannerService:
    def __init__(self, db: Session):
        self.db = db
        self.plan_service = PlanService(db)
        self.goal_evaluator = GoalEvaluatorService(db)

    def get_or_create_plan(
        self,
        viewer_internal_id: str,
        viewer_state: ViewerState,
        trigger_type: str = "app_open"
    ) -> Tuple[Optional[Plan], Optional[GoalEvaluationResult], bool, str]:
        """Fetch existing valid active plan or evaluate/create new active plan.

        Returns (plan, eval_result, is_reused, rationale).
        """
        active_plan = self.plan_service.get_active_plan(viewer_internal_id)

        # Handle subscription purchase event replanning: cancel free-tier plans upon purchase
        if viewer_state.subscription_status == "SUBSCRIBED" and active_plan:
            goal = self.db.execute(select(Goal).where(Goal.id == active_plan.goal_id)).scalar_one_or_none()
            rules = json.loads(goal.rules_json) if (goal and goal.rules_json) else {}
            if rules.get("free_tier_only", True) or "free_tier" in (goal.description or "").lower():
                active_plan.plan_status = "CANCELLED"
                active_plan.deactivated_at = utc_now()
                self.db.commit()
                logger.info(f"Cancelled active plan {active_plan.id} for viewer {viewer_internal_id} due to verified purchase.")
                active_plan = None

        # Re-evaluate goal
        selected_eval, sel_rationale = self.goal_evaluator.select_best_goal(viewer_internal_id, viewer_state)

        if not selected_eval:
            if active_plan:
                # Cancel existing plan if no goal is eligible anymore
                active_plan.plan_status = "CANCELLED"
                active_plan.deactivated_at = utc_now()
                self.db.commit()
            return None, None, False, f"Abstained from plan creation: {sel_rationale}"

        # If existing active plan matches selected goal, REUSE existing plan!
        if active_plan and active_plan.goal_id == selected_eval.goal_id:
            return active_plan, selected_eval, True, f"Reusing existing active plan {active_plan.id} for goal '{selected_eval.goal_code}' v{selected_eval.version}."

        # Create new active plan, replacing previous
        steps = [
            {
                "step_number": 1,
                "action_type": "INTERVENTION_EVALUATION",
                "recommended_category": "Drama"
            },
            {
                "step_number": 2,
                "action_type": "HOMEPAGE_BANNER_PROMOTION",
                "target_dialect": viewer_state.dialect_preference or "Egyptian Arabic"
            }
        ]

        new_plan = self.plan_service.create_plan(
            viewer_internal_id=viewer_internal_id,
            goal_id=selected_eval.goal_id,
            steps=steps,
            replace_existing=True
        )

        return new_plan, selected_eval, False, f"Created new active plan for goal '{selected_eval.goal_code}' v{selected_eval.version}."
