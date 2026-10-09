import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from ott_agent.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Viewer(Base):
    __tablename__ = "viewers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    viewer_id = Column(String(64), unique=True, nullable=False, index=True)
    external_id = Column(String(128), unique=True, nullable=True, index=True)
    profile_version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    states = relationship("ViewerState", back_populates="viewer", cascade="all, delete-orphan")
    facts = relationship("ViewerFact", back_populates="viewer", cascade="all, delete-orphan")
    plans = relationship("Plan", back_populates="viewer", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="viewer")
    decisions = relationship("Decision", back_populates="viewer", cascade="all, delete-orphan")


class ViewerState(Base):
    __tablename__ = "viewer_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    dialect_preference = Column(String(64), nullable=True)
    language_variant = Column(String(32), nullable=True)
    engagement_score = Column(Float, default=0.0, nullable=False)
    subscription_status = Column(String(32), default="FREE", nullable=False)  # FREE, SUBSCRIBED
    state_snapshot_json = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    viewer = relationship("Viewer", back_populates="states")


class ViewerFact(Base):
    __tablename__ = "viewer_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_type = Column(String(64), nullable=False)
    fact_key = Column(String(128), nullable=False)
    fact_value = Column(Text, nullable=False)
    evidence_event_id = Column(String(64), nullable=True)
    source_type = Column(String(64), nullable=False, default="unknown")  # app_settings, purchase_event, profile, watch_event
    source_record_id = Column(String(128), nullable=True)
    observation_time = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    received_time = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    has_conflict = Column(Boolean, default=False, nullable=False)
    conflict_details_json = Column(Text, nullable=True)
    resolution_rule = Column(String(128), nullable=True)
    resolution_reason = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    viewer = relationship("Viewer", back_populates="facts")
