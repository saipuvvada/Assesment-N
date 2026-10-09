import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Integer, Boolean
from sqlalchemy.orm import relationship

from ott_agent.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)

    trigger_type = Column(String(64), default="app_open", nullable=False)
    trigger_event_id = Column(String(64), nullable=True)
    trigger_event_age_seconds = Column(Float, nullable=True)

    goal_id = Column(String(64), nullable=True)
    rule_version = Column(Integer, default=1, nullable=False)
    deadline_timestamp = Column(DateTime(timezone=True), nullable=True)
    success_signal = Column(String(128), nullable=True)

    decision_type = Column(String(64), nullable=False)
    recommended_action = Column(String(128), nullable=False)
    selected_dialect = Column(String(64), nullable=True)
    dialect_source = Column(String(64), nullable=True)
    content_references_json = Column(Text, nullable=False, default="[]")

    confidence_score = Column(Float, default=1.0, nullable=False)
    rationale = Column(Text, nullable=False)
    evidence_refs_json = Column(Text, nullable=False, default="[]")
    evidence_freshness_json = Column(Text, nullable=False, default="{}")

    assumptions_json = Column(Text, nullable=False, default="[]")
    conflicts_json = Column(Text, nullable=False, default="[]")

    passed_checks_json = Column(Text, nullable=False, default="[]")
    failed_checks_json = Column(Text, nullable=False, default="[]")

    decision_latency_ms = Column(Float, default=0.0, nullable=False)
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, NO_ACTION, ABSTAINED, REJECTED
    abstention_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    plan = relationship("Plan", back_populates="decisions")
    viewer = relationship("Viewer", back_populates="decisions")
    actions = relationship("Action", back_populates="decision")


class Action(Base):
    __tablename__ = "actions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id = Column(String(36), ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    action_type = Column(String(64), nullable=False)  # HOMEPAGE_ROW, HERO_PLACEMENT, PUSH_NOTIFICATION, WHATSAPP_TEMPLATE, IN_APP_MESSAGE, NO_ACTION
    payload_json = Column(Text, nullable=False, default="{}")
    verification_status = Column(String(32), default="VERIFIED", nullable=False)  # VERIFIED, REJECTED
    verification_failed_reasons_json = Column(Text, nullable=False, default="[]")
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, EXECUTED, FAILED, REJECTED
    verification_result_json = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    decision = relationship("Decision", back_populates="actions")
    viewer = relationship("Viewer")
    outcomes = relationship("Outcome", back_populates="action")


class Outcome(Base):
    __tablename__ = "outcomes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id = Column(String(36), ForeignKey("actions.id", ondelete="SET NULL"), nullable=True, index=True)
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name = Column(String(64), nullable=False)
    metric_value = Column(Float, nullable=False)
    outcome_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    metadata_json = Column(Text, nullable=True)

    action = relationship("Action", back_populates="outcomes")
    viewer = relationship("Viewer")
