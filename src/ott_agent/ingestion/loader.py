import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def load_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load records from CSV, JSON, or JSONL file into a list of dicts."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    records: List[Dict[str, Any]] = []

    if suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = [data]
    elif suffix == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    records.append(json.loads(line_str))
                except json.JSONDecodeError as e:
                    records.append({"_malformed_raw": line_str, "_line_no": line_no, "_error": str(e)})
    elif suffix == ".csv":
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            records = [dict(row) for row in reader]
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    return records
