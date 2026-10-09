import json
from typing import Dict, Any, Tuple, Optional


def validate_raw_event(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate raw event record structure.

    Returns (is_valid, error_reason).
    """
    if not isinstance(record, dict):
        return False, "Record must be a JSON object"

    source = record.get("source")
    if not source or not str(source).strip():
        return False, "Missing or empty 'source' field"

    event_type = record.get("event_type")
    if not event_type or not str(event_type).strip():
        return False, "Missing or empty 'event_type' field"

    ts = record.get("timestamp") or record.get("event_timestamp")
    if not ts or str(ts).strip() in ("", "invalid-date"):
        return False, "Missing or invalid 'timestamp' field"

    return True, None


def validate_catalogue_item(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate catalogue item record."""
    if not isinstance(record, dict):
        return False, "Catalogue record must be an object/row dict"

    content_id = record.get("content_id")
    if not content_id or not str(content_id).strip():
        return False, "Missing content_id"

    title = record.get("title")
    if not title or not str(title).strip():
        return False, "Missing title"

    return True, None
