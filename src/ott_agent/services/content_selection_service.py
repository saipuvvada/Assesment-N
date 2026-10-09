import re
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.catalogue import ContentItem
from ott_agent.services.evidence_service import EvidenceService

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


# Regex patterns to detect prompt injection attempts in untrusted content descriptions
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all)\s+rules", re.IGNORECASE),
    re.compile(r"message\s+every\s+viewer", re.IGNORECASE),
    re.compile(r"grant\s+subscription", re.IGNORECASE),
    re.compile(r"override\s+consent", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE)
]


class ContentSelectionService:
    def __init__(self, db: Session):
        self.db = db
        self.evidence_service = EvidenceService(db)

    def is_text_prompt_injection(self, text: str) -> bool:
        """Check if untrusted text contains prompt injection attempts."""
        if not text:
            return False
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def select_homepage_row(
        self,
        viewer_internal_id: str,
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, List[ContentItem], Optional[str]]:
        """Select a homepage row containing at least 3 eligible titles matching dialect and availability.

        Returns (is_valid, content_items, error_reason).
        """
        now = current_time or utc_now()

        # 1. Resolve actual app dialect using evidence precedence
        eff_dialect, dialect_src, _, _ = self.evidence_service.resolve_effective_fact(
            viewer_internal_id, "dialect_preference"
        )
        selected_dialect = eff_dialect or "Egyptian Arabic"

        # 2. Fetch all catalogue items
        items = self.db.execute(select(ContentItem)).scalars().all()

        eligible_items: List[ContentItem] = []
        seen_titles = set()

        for item in items:
            # Security check: ignore items with malicious embedded instructions
            meta_str = str(item.metadata_json or "")
            if self.is_text_prompt_injection(item.title) or self.is_text_prompt_injection(meta_str):
                logger.warning(f"Rejected catalogue item '{item.content_id}' due to prompt injection attempt in title/metadata.")
                continue

            # Availability window check
            start_t = item.availability_start.replace(tzinfo=timezone.utc) if item.availability_start.tzinfo is None else item.availability_start
            end_t = item.availability_end.replace(tzinfo=timezone.utc) if item.availability_end.tzinfo is None else item.availability_end

            if not (start_t <= now <= end_t):
                continue

            # Dialect matching check
            if item.dialect != selected_dialect:
                continue

            # Deduplicate alternate title variants
            base_title = item.title.strip().lower()
            if base_title in seen_titles:
                continue

            seen_titles.add(base_title)
            eligible_items.append(item)

        # Minimum of 3 valid titles for homepage row
        if len(eligible_items) < 3:
            return False, eligible_items, f"Insufficient valid titles ({len(eligible_items)} < 3 required) for dialect '{selected_dialect}' at time {now.isoformat()}."

        return True, eligible_items, None
