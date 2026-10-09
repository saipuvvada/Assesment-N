from typing import List, Dict, Any
from pydantic import BaseModel


class IngestionSummary(BaseModel):
    source_file: str
    total_records: int
    processed_records: int
    duplicates_detected: int
    rejected_records: int
    errors: List[str] = []
