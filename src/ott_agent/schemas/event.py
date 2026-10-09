from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class EventIngestSchema(BaseModel):
    event_id: str = Field(..., description="Unique event identifier from source")
    viewer_id: Optional[str] = None
    source: str
    event_type: str
    timestamp: str = Field(..., description="Raw ISO 8601 string or timestamp")
    payload: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class EventResponse(BaseModel):
    id: str
    event_id: Optional[str]
    viewer_id: Optional[str]
    source: str
    event_type: str
    event_timestamp: datetime
    ingested_at: datetime
    raw_timestamp: Optional[str]
    is_duplicate: bool

    model_config = ConfigDict(from_attributes=True)


class RejectedEventSchema(BaseModel):
    id: int
    source: str
    raw_data: str
    error_reason: str
    rejected_at: datetime

    model_config = ConfigDict(from_attributes=True)
