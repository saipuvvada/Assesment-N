import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.goal import Goal
from ott_agent.models.viewer import ViewerState
from ott_agent.services.evidence_service import EvidenceService

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


KNOWN_UNDERSPECIFIED_GOALS = {"UNDERSPECIFIED_GENRE_BOOST", "UNDERSPECIFIED_REENGAGE_V1"}
KNOWN_UNAVAILABLE_SIGNALS = {"churn_risk_score", "user_cancellation_intent_event"}


class GoalEvaluationResult:
    def __init__(
        self,
        goal_id: str,
        goal_code: str,
        version: int,
        is_eligible: bool,
        is_supported: bool,
        is_specified: bool,
        deadline_timestamp: Optional[datetime],
        success_signal: str,
        exclusion_reasons: List[str],
        eligibility_evidence: List[str]
    ):
        self.goal_id = goal_id
        self.goal_code = goal_code
        self.version = version
        self.is_eligible = is_eligible
        self.is_supported = is_supported
        self.is_specified = is_specified
        self.deadline_timestamp = deadline_timestamp
        self.success_signal = success_signal
        self.exclusion_reasons = exclusion_reasons
        self.eligibility_evidence = eligibility_evidence


class GoalEvaluatorService:
    def __init__(self, db: Session):
        self.db = db
        self.evidence_service = EvidenceService(db)

    def get_all_goals(self) -> List[Goal]:
        stmt = select(Goal).order_by(Goal.version.desc())
        return list(self.db.execute(stmt).scalars().all())

    def evaluate_goal_for_viewer(
        self,
        goal: Goal,
        viewer_internal_id: str,
        viewer_state: ViewerState
    ) -> GoalEvaluationResult:
        rules = json.loads(goal.rules_json) if goal.rules_json else {}
        code = goal.goal_code
        version = goal.version

        # 1. Check if goal is underspecified
        is_specified = code not in KNOWN_UNDERSPECIFIED_GOALS and "min_engagement_threshold" in rules or "target_dialect" in rules or code.startswith("DIALECT_")

        # 2. Check if success signal is available in stream
        req_signal = rules.get("success_signal", "watch_complete")
        is_supported = req_signal not in KNOWN_UNAVAILABLE_SIGNALS

        exclusion_reasons = []
        eligibility_evidence = []

        if not is_specified:
            exclusion_reasons.append(f"Goal '{code}' is underspecified (lacks explicit thresholds/bounds). Conservative policy applied.")

        if not is_supported:
            exclusion_reasons.append(f"Goal '{code}' requires unavailable success signal '{req_signal}'. Marked unsupported.")

        # 3. Check viewer state eligibility & dialect matching
        eff_dialect, dialect_src, has_conflict, _ = self.evidence_service.resolve_effective_fact(
            viewer_internal_id, "dialect_preference"
        )
        current_dialect = eff_dialect or viewer_state.dialect_preference or "Egyptian Arabic"

        target_dialect = rules.get("target_dialect")
        if target_dialect and target_dialect != current_dialect:
            exclusion_reasons.append(f"Viewer effective dialect '{current_dialect}' (src: {dialect_src}) does not match target dialect '{target_dialect}'.")

        # Check engagement score threshold
        min_eng = rules.get("min_engagement_threshold", 0.0)
        if viewer_state.engagement_score < min_eng:
            exclusion_reasons.append(f"Viewer engagement score {viewer_state.engagement_score} below required threshold {min_eng}.")
        else:
            eligibility_evidence.append(f"engagement_score:{viewer_state.engagement_score}>={min_eng}")

        # Check subscription exclusions if goal is for free tier users
        if rules.get("free_tier_only", False) and viewer_state.subscription_status == "SUBSCRIBED":
            exclusion_reasons.append("Viewer is already SUBSCRIBED; free-tier goal excluded.")

        is_eligible = is_specified and is_supported and len(exclusion_reasons) == 0

        # Calculate deadline
        cooldown_hours = rules.get("cooldown_hours", 24)
        deadline = utc_now() + timedelta(hours=cooldown_hours)

        return GoalEvaluationResult(
            goal_id=goal.id,
            goal_code=code,
            version=version,
            is_eligible=is_eligible,
            is_supported=is_supported,
            is_specified=is_specified,
            deadline_timestamp=deadline,
            success_signal=req_signal,
            exclusion_reasons=exclusion_reasons,
            eligibility_evidence=eligibility_evidence
        )

    def select_best_goal(
        self,
        viewer_internal_id: str,
        viewer_state: ViewerState
    ) -> Tuple[Optional[GoalEvaluationResult], str]:
        """Select single eligible goal according to deterministic priority policy."""
        goals = self.get_all_goals()
        if not goals:
            return None, "No goal definitions found in catalogue."

        evaluations = [self.evaluate_goal_for_viewer(g, viewer_internal_id, viewer_state) for g in goals]
        eligible_evals = [e for e in evaluations if e.is_eligible]

        if not eligible_evals:
            reasons = "; ".join([f"[{e.goal_code} v{e.version}: {', '.join(e.exclusion_reasons)}]" for e in evaluations])
            return None, f"No eligible goals available for viewer. Reasons: {reasons}"

        # Deterministic Priority Ordering:
        # Highest priority to highest version retention goals matching dialect, then cross-dialect boost
        sorted_eligible = sorted(
            eligible_evals,
            key=lambda e: (e.goal_code.startswith("DIALECT_RETENTION"), e.version),
            reverse=True
        )

        selected = sorted_eligible[0]
        return selected, f"Selected goal '{selected.goal_code}' v{selected.version} based on highest version dialect retention match."
