from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class ContentItemSchema(BaseModel):
    id: str
    content_id: str
    title: str
    dialect: str
    language_variant: str
    availability_start: datetime
    availability_end: datetime
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
