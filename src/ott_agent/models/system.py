from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Text

from ott_agent.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ReplayCheckpoint(Base):
    __tablename__ = "replay_checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    last_processed_event_id = Column(String(64), nullable=False)
    checkpoint_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class ProcessingError(Base):
    __tablename__ = "processing_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component = Column(String(64), nullable=False, index=True)
    error_message = Column(Text, nullable=False)
    traceback = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class LatencyMeasurement(Base):
    __tablename__ = "latency_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation = Column(String(64), nullable=False, index=True)
    duration_ms = Column(Float, nullable=False)
    measured_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
