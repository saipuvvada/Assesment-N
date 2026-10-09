import json
import logging
from datetime import datetime, timezone
from typing import Tuple, List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.decision import Decision, Action
from ott_agent.models.goal import Plan, Goal
from ott_agent.models.viewer import Viewer, ViewerState
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.evidence_service import EvidenceService
from ott_agent.services.content_selection_service import ContentSelectionService
from ott_agent.services.messaging_service import MessagingControlService

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


class VerificationService:
    """Dedicated independent action verification service querying trusted DB records."""

    def __init__(self, db: Session):
        self.db = db
        self.viewer_service = ViewerService(db)
        self.evidence_service = EvidenceService(db)
        self.content_service = ContentSelectionService(db)
        self.messaging_service = MessagingControlService(db)

    def verify_action(
        self,
        decision_id: str,
        action_type: str,
        proposed_payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        execution_time: Optional[datetime] = None
    ) -> Tuple[bool, List[str]]:
        """Perform 100% independent verification querying trusted DB records."""
        reasons = []
        now = execution_time or utc_now()

        # 1. Fetch decision record
        stmt_dec = select(Decision).where(Decision.id == decision_id)
        decision = self.db.execute(stmt_dec).scalar_one_or_none()
        if not decision:
            return False, [f"Decision ID '{decision_id}' not found in database."]

        viewer_internal_id = decision.viewer_id

        # 2. Check Idempotency key: prevent duplicate action execution
        if idempotency_key:
            stmt_idem = select(Action).where(Action.idempotency_key == idempotency_key)
            existing_act = self.db.execute(stmt_idem).scalar_one_or_none()
            if existing_act:
                reasons.append(f"Duplicate trigger/action detected with idempotency_key '{idempotency_key}'.")

        # 3. Check Active Plan and Deadline
        if decision.plan_id:
            stmt_plan = select(Plan).where(Plan.id == decision.plan_id)
            plan = self.db.execute(stmt_plan).scalar_one_or_none()
            if not plan or plan.plan_status != "ACTIVE":
                reasons.append(f"Plan ID '{decision.plan_id}' is no longer ACTIVE.")

        if decision.deadline_timestamp:
            d_time = decision.deadline_timestamp.replace(tzinfo=timezone.utc) if decision.deadline_timestamp.tzinfo is None else decision.deadline_timestamp
            if now > d_time:
                reasons.append(f"Action deadline ({d_time.isoformat()}) expired prior to execution at {now.isoformat()}.")

        # 4. Intervention-Specific Checks
        if action_type in ("HOMEPAGE_ROW", "HOMEPAGE_BANNER_PROMOTION"):
            # Verify homepage row has at least 3 eligible titles
            valid_row, items, row_err = self.content_service.select_homepage_row(
                viewer_internal_id=viewer_internal_id,
                current_time=now
            )
            if not valid_row:
                reasons.append(f"Homepage verification failed: {row_err}")

        elif action_type in ("PUSH_NOTIFICATION", "WHATSAPP_TEMPLATE"):
            # Verify messaging controls (quiet hours 22:00-08:00, channel consent, 1 msg/day limit)
            channel = "push" if action_type == "PUSH_NOTIFICATION" else "whatsapp"
            msg_ok, msg_reasons = self.messaging_service.check_messaging_rules(
                viewer_internal_id=viewer_internal_id,
                channel=channel,
                execution_time=now
            )
            if not msg_ok:
                reasons.extend(msg_reasons)

        is_verified = len(reasons) == 0
        return is_verified, reasons
