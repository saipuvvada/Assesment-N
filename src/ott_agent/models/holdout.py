import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, UniqueConstraint

from ott_agent.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class HoldoutAssignment(Base):
    __tablename__ = "holdout_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    experiment_id = Column(String(64), nullable=False, index=True)
    group_name = Column(String(32), nullable=False)  # treatment, control, holdout
    assigned_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("viewer_id", "experiment_id", name="uq_viewer_experiment"),
    )


class PilotData(Base):
    __tablename__ = "pilot_data"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    experiment_id = Column(String(64), nullable=False, index=True)
    viewer_id = Column(String(36), ForeignKey("viewers.id", ondelete="CASCADE"), nullable=False, index=True)
    metrics_json = Column(Text, nullable=False)
    recorded_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
