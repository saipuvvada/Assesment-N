import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.decision import Action
from ott_agent.services.messaging_service import MessagingControlService

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


class MockActionExecutorService:
    """Local mock action executor for replay without external network calls."""

    def __init__(self, db: Session):
        self.db = db
        self.messaging_service = MessagingControlService(db)

    def execute_action(
        self,
        action_id: str,
        is_verified: bool,
        verification_failed_reasons: List[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Execute action locally and persist execution status and message delivery history.

        Returns (status, result_dict).
        """
        stmt = select(Action).where(Action.id == action_id)
        action = self.db.execute(stmt).scalar_one_or_none()

        if not action:
            raise ValueError(f"Action '{action_id}' not found in database.")

        if not is_verified:
            action.verification_status = "REJECTED"
            action.verification_failed_reasons_json = json.dumps(verification_failed_reasons)
            action.status = "REJECTED"
            action.verification_result_json = json.dumps({
                "verified": False,
                "rejection_reasons": verification_failed_reasons
            })
            self.db.commit()
            self.db.refresh(action)
            return "REJECTED", {"executed": False, "reason": "Verification failed", "reasons": verification_failed_reasons}

        # Action is verified -> execute mock action
        action.verification_status = "VERIFIED"
        action.verification_failed_reasons_json = "[]"
        action.status = "EXECUTED"

        result_payload = {
            "executed": True,
            "action_type": action.action_type,
            "executed_at": utc_now().isoformat(),
            "mock_execution_mode": "LOCAL_REPLAY"
        }

        # If action is a message intervention, record delivery in MessageDelivery
        if action.action_type in ("PUSH_NOTIFICATION", "WHATSAPP_TEMPLATE"):
            channel = "push" if action.action_type == "PUSH_NOTIFICATION" else "whatsapp"
            delivery = self.messaging_service.record_message_delivery(
                viewer_internal_id=action.viewer_id,
                message_id=action.id,
                channel=channel,
                status="DELIVERED"
            )
            result_payload["delivery_id"] = delivery.id

        action.verification_result_json = json.dumps(result_payload)
        self.db.commit()
        self.db.refresh(action)

        return "EXECUTED", result_payload
