import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ott_agent.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Goal(Base):
    __tablename__ = "goals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    goal_code = Column(String(64), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    description = Column(Text, nullable=True)
    rules_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("goal_code", "version", name="uq_goal_code_version"),
    )

    plans = relationship("Plan", back_populates="goal")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    goal_id = Column(String(36), ForeignKey("goals.id", ondelete="RESTRICT"), nullable=False)
    plan_status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, COMPLETED, CANCELLED
    steps_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    viewer = relationship("Viewer", back_populates="plans")
    goal = relationship("Goal", back_populates="plans")
    decisions = relationship("Decision", back_populates="plan")
