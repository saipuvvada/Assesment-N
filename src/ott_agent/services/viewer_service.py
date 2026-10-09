import json
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.models.viewer import Viewer, ViewerState, ViewerFact

logger = logging.getLogger(__name__)


class ViewerService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_viewer_id(self, viewer_id: str) -> Optional[Viewer]:
        """Fetch viewer by viewer_id string."""
        stmt = select(Viewer).where(Viewer.viewer_id == viewer_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_or_update_viewer(
        self,
        viewer_id: str,
        external_id: Optional[str] = None,
        profile_version: int = 1,
        dialect_preference: Optional[str] = None,
        language_variant: Optional[str] = None,
        engagement_score: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Viewer:
        """Create a viewer or update profile with version conflict resolution."""
        existing = self.get_by_viewer_id(viewer_id)
        if existing:
            # Profile conflict resolution: update if newer or equal profile version
            if profile_version >= existing.profile_version:
                existing.profile_version = profile_version
                if external_id:
                    existing.external_id = external_id
                self.db.flush()

            # Update latest viewer state
            state = ViewerState(
                viewer_id=existing.id,
                dialect_preference=dialect_preference,
                language_variant=language_variant,
                engagement_score=engagement_score,
                state_snapshot_json=json.dumps(metadata or {})
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            viewer = Viewer(
                viewer_id=viewer_id,
                external_id=external_id,
                profile_version=profile_version
            )
            self.db.add(viewer)
            self.db.flush()

            state = ViewerState(
                viewer_id=viewer.id,
                dialect_preference=dialect_preference,
                language_variant=language_variant,
                engagement_score=engagement_score,
                state_snapshot_json=json.dumps(metadata or {})
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(viewer)
            return viewer

    def get_latest_state(self, viewer_internal_id: str) -> Optional[ViewerState]:
        """Get the latest state snapshot for a viewer."""
        stmt = (
            select(ViewerState)
            .where(ViewerState.viewer_id == viewer_internal_id)
            .order_by(ViewerState.updated_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def record_fact(
        self,
        viewer_internal_id: str,
        fact_type: str,
        fact_key: str,
        fact_value: str,
        evidence_event_id: Optional[str] = None,
        confidence: float = 1.0
    ) -> ViewerFact:
        """Record a fact with explicit evidence provenance."""
        fact = ViewerFact(
            viewer_id=viewer_internal_id,
            fact_type=fact_type,
            fact_key=fact_key,
            fact_value=fact_value,
            evidence_event_id=evidence_event_id,
            confidence=confidence
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)
        return fact

    def get_viewer_facts(self, viewer_internal_id: str) -> List[ViewerFact]:
        """Fetch all facts recorded for a viewer."""
        stmt = select(ViewerFact).where(ViewerFact.viewer_id == viewer_internal_id)
        return list(self.db.execute(stmt).scalars().all())
