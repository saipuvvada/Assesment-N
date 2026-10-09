from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict


class ViewerStateSchema(BaseModel):
    dialect_preference: Optional[str] = None
    language_variant: Optional[str] = None
    engagement_score: float = 0.0
    state_snapshot: Optional[Dict[str, Any]] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ViewerFactSchema(BaseModel):
    fact_type: str
    fact_key: str
    fact_value: str
    evidence_event_id: Optional[str] = None
    confidence: float = 1.0
    version: int = 1
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ViewerProfileResponse(BaseModel):
    id: str
    viewer_id: str
    external_id: Optional[str] = None
    profile_version: int
    created_at: datetime
    updated_at: datetime
    current_state: Optional[ViewerStateSchema] = None

    model_config = ConfigDict(from_attributes=True)


class ViewerProfileCreate(BaseModel):
    viewer_id: str
    external_id: Optional[str] = None
    profile_version: int = 1
    dialect_preference: Optional[str] = None
    language_variant: Optional[str] = None
    engagement_score: float = 0.0
