import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from ott_agent.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(64), nullable=True, index=True)
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="SET NULL"), nullable=True, index=True)
    source = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    payload_json = Column(Text, nullable=False)
    raw_timestamp = Column(String(128), nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    deduplication_hash = Column(String(64), unique=True, nullable=False, index=True)
    is_duplicate = Column(Boolean, default=False, nullable=False)

    viewer = relationship("Viewer", back_populates="events")


class RejectedEvent(Base):
    __tablename__ = "rejected_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(64), nullable=False)
    raw_data = Column(Text, nullable=False)
    error_reason = Column(Text, nullable=False)
    rejected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
