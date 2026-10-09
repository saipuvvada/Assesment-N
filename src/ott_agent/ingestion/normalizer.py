import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from dateutil import parser as date_parser


def normalize_timestamp(ts_val: Any) -> Tuple[datetime, str]:
    """Parse raw timestamp into UTC aware datetime and return (utc_dt, raw_ts_str).

    Raises ValueError if timestamp cannot be parsed.
    """
    if ts_val is None:
        raise ValueError("Timestamp is missing")

    raw_str = str(ts_val).strip()
    if not raw_str:
        raise ValueError("Timestamp is empty")

    try:
        # Check if numeric timestamp (seconds or milliseconds)
        if raw_str.isdigit() or (raw_str.replace('.', '', 1).isdigit() and raw_str.count('.') <= 1):
            val = float(raw_str)
            if val > 1e11:  # milliseconds
                val = val / 1000.0
            dt = datetime.fromtimestamp(val, tz=timezone.utc)
            return dt, raw_str

        # Parse string ISO format
        dt = date_parser.parse(raw_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt, raw_str
    except Exception as e:
        raise ValueError(f"Invalid timestamp format '{ts_val}': {e}")


def compute_deduplication_hash(
    source: str,
    event_id: Optional[str],
    event_type: str,
    viewer_id: Optional[str],
    raw_timestamp: str,
    payload: Dict[str, Any]
) -> str:
    """Compute stable SHA-256 deduplication hash for an event record."""
    if event_id and str(event_id).strip():
        key = f"ID:{source}:{str(event_id).strip()}"
    else:
        payload_str = json.dumps(payload, sort_keys=True)
        key = f"PAYLOAD:{source}:{event_type}:{viewer_id or 'anon'}:{raw_timestamp}:{payload_str}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
