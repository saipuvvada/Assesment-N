from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict


class DecisionSchema(BaseModel):
    id: str
    viewer_id: str
    plan_id: Optional[str] = None
    decision_type: str
    recommended_action: str
    rationale: str
    evidence_refs: List[Any] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionSchema(BaseModel):
    id: str
    decision_id: str
    viewer_id: str
    action_type: str
    status: str
    payload: Dict[str, Any] = {}
    verification_result: Optional[Dict[str, Any]] = None
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OutcomeSchema(BaseModel):
    id: str
    action_id: Optional[str] = None
    viewer_id: str
    metric_name: str
    metric_value: float
    outcome_timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
