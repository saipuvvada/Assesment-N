import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint

from ott_agent.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(256), nullable=False)
    dialect = Column(String(64), nullable=False, index=True)
    language_variant = Column(String(32), nullable=False)
    availability_start = Column(DateTime(timezone=True), nullable=False)
    availability_end = Column(DateTime(timezone=True), nullable=False)
    category = Column(String(64), nullable=True)
    metadata_json = Column(Text, nullable=True)


class MessageConsent(Base):
    __tablename__ = "message_consents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(32), nullable=False)  # push, email, sms
    consent_given = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("viewer_id", "channel", name="uq_viewer_channel_consent"),
    )


class MessageDelivery(Base):
    __tablename__ = "message_deliveries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(String(64), nullable=False)
    channel = Column(String(32), nullable=False)
    sent_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    status = Column(String(32), default="DELIVERED", nullable=False)
