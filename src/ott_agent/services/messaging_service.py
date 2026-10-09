import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ott_agent.models.catalogue import MessageConsent, MessageDelivery
from ott_agent.models.viewer import ViewerState

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


class MessagingControlService:
    def __init__(self, db: Session):
        self.db = db

    def check_messaging_rules(
        self,
        viewer_internal_id: str,
        channel: str,
        execution_time: Optional[datetime] = None,
        local_utc_offset_hours: int = 0
    ) -> Tuple[bool, List[str]]:
        """Verify messaging quiet hours (22:00-08:00 local time), channel consent, and 1 msg/day limit.

        Returns (is_allowed, failure_reasons).
        """
        reasons = []
        now = execution_time or utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Calculate local viewer time
        local_time = now + timedelta(hours=local_utc_offset_hours)
        local_hour = local_time.hour
        local_date_str = local_time.strftime("%Y-%m-%d")

        # 1. Quiet hours enforcement (22:00 to 08:00)
        if local_hour >= 22 or local_hour < 8:
            reasons.append(
                f"Quiet hours policy violation: Local time is {local_time.strftime('%H:%M')} "
                f"(Quiet hours are 22:00 to 08:00)."
            )

        # 2. Channel consent enforcement
        stmt_consent = select(MessageConsent).where(
            MessageConsent.viewer_id == viewer_internal_id,
            MessageConsent.channel == channel
        )
        consent = self.db.execute(stmt_consent).scalar_one_or_none()
        if consent and not consent.consent_given:
            reasons.append(f"Channel consent denied for channel '{channel}'.")

        # 3. Rate limit: At most 1 message per viewer per local calendar day
        stmt_del = select(MessageDelivery).where(
            MessageDelivery.viewer_id == viewer_internal_id,
            MessageDelivery.channel == channel,
            MessageDelivery.status == "DELIVERED"
        )
        deliveries = self.db.execute(stmt_del).scalars().all()

        same_day_count = 0
        for d in deliveries:
            d_time = d.sent_at.replace(tzinfo=timezone.utc) if d.sent_at.tzinfo is None else d.sent_at
            d_local_date = (d_time + timedelta(hours=local_utc_offset_hours)).strftime("%Y-%m-%d")
            if d_local_date == local_date_str:
                same_day_count += 1

        if same_day_count >= 1:
            reasons.append(
                f"Daily frequency limit exceeded: Viewer has already received {same_day_count} "
                f"message(s) on local date {local_date_str} for channel '{channel}'."
            )

        is_allowed = len(reasons) == 0
        return is_allowed, reasons

    def record_message_delivery(
        self,
        viewer_internal_id: str,
        message_id: str,
        channel: str,
        status: str = "DELIVERED"
    ) -> MessageDelivery:
        """Record explicit message delivery history."""
        delivery = MessageDelivery(
            viewer_id=viewer_internal_id,
            message_id=message_id,
            channel=channel,
            sent_at=utc_now(),
            status=status
        )
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery
