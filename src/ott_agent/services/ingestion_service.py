import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from dateutil import parser as date_parser

from ott_agent.ingestion.loader import load_file
from ott_agent.ingestion.normalizer import normalize_timestamp, compute_deduplication_hash
from ott_agent.ingestion.validator import validate_raw_event, validate_catalogue_item
from ott_agent.models.viewer import Viewer, ViewerState, ViewerFact
from ott_agent.models.event import Event, RejectedEvent
from ott_agent.models.catalogue import ContentItem
from ott_agent.models.goal import Goal
from ott_agent.models.holdout import HoldoutAssignment, PilotData
from ott_agent.schemas.ingestion import IngestionSummary
from ott_agent.services.viewer_service import ViewerService

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.viewer_service = ViewerService(db)

    def ingest_viewers(self, file_path: Path) -> IngestionSummary:
        records = load_file(file_path)
        total = len(records)
        processed = 0
        rejected = 0
        duplicates = 0
        errors: List[str] = []

        for rec in records:
            if "_error" in rec:
                self._record_rejection("viewers", str(rec), rec["_error"])
                rejected += 1
                errors.append(f"Line {rec.get('_line_no')}: {rec['_error']}")
                continue

            v_id = rec.get("viewer_id")
            if not v_id:
                self._record_rejection("viewers", str(rec), "Missing viewer_id")
                rejected += 1
                continue

            try:
                self.viewer_service.create_or_update_viewer(
                    viewer_id=str(v_id),
                    external_id=rec.get("external_id"),
                    profile_version=int(rec.get("profile_version", 1)),
                    dialect_preference=rec.get("dialect_preference"),
                    language_variant=rec.get("language_variant"),
                    engagement_score=float(rec.get("engagement_score", 0.0)),
                    metadata=rec
                )
                processed += 1
            except Exception as e:
                self._record_rejection("viewers", str(rec), str(e))
                rejected += 1
                errors.append(str(e))

        return IngestionSummary(
            source_file=str(file_path),
            total_records=total,
            processed_records=processed,
            duplicates_detected=duplicates,
            rejected_records=rejected,
            errors=errors
        )

    def ingest_catalogue(self, file_path: Path) -> IngestionSummary:
        records = load_file(file_path)
        total = len(records)
        processed = 0
        rejected = 0
        duplicates = 0
        errors: List[str] = []

        for rec in records:
            valid, err = validate_catalogue_item(rec)
            if not valid:
                self._record_rejection("catalogue", str(rec), err or "Invalid item")
                rejected += 1
                errors.append(err or "Invalid item")
                continue

            c_id = rec["content_id"]
            existing = self.db.execute(select(ContentItem).where(ContentItem.content_id == c_id)).scalar_one_or_none()

            try:
                start_dt, _ = normalize_timestamp(rec.get("availability_start", "2026-01-01T00:00:00Z"))
                end_dt, _ = normalize_timestamp(rec.get("availability_end", "2026-12-31T23:59:59Z"))

                if existing:
                    existing.title = rec["title"]
                    existing.dialect = rec.get("dialect", "Standard Arabic")
                    existing.language_variant = rec.get("language_variant", "ar")
                    existing.availability_start = start_dt
                    existing.availability_end = end_dt
                    existing.category = rec.get("category")
                    existing.metadata_json = json.dumps(rec)
                    duplicates += 1
                else:
                    item = ContentItem(
                        content_id=c_id,
                        title=rec["title"],
                        dialect=rec.get("dialect", "Standard Arabic"),
                        language_variant=rec.get("language_variant", "ar"),
                        availability_start=start_dt,
                        availability_end=end_dt,
                        category=rec.get("category"),
                        metadata_json=json.dumps(rec)
                    )
                    self.db.add(item)
                processed += 1
            except Exception as e:
                self._record_rejection("catalogue", str(rec), str(e))
                rejected += 1
                errors.append(str(e))

        self.db.commit()
        return IngestionSummary(
            source_file=str(file_path),
            total_records=total,
            processed_records=processed,
            duplicates_detected=duplicates,
            rejected_records=rejected,
            errors=errors
        )

    def ingest_goal_rules(self, file_path: Path) -> IngestionSummary:
        records = load_file(file_path)
        total = len(records)
        processed = 0
        rejected = 0
        duplicates = 0
        errors: List[str] = []

        for rec in records:
            code = rec.get("goal_code")
            version = rec.get("version", 1)
            if not code:
                self._record_rejection("goal_rules", str(rec), "Missing goal_code")
                rejected += 1
                continue

            existing = self.db.execute(
                select(Goal).where(Goal.goal_code == code, Goal.version == int(version))
            ).scalar_one_or_none()

            if existing:
                existing.description = rec.get("description")
                existing.rules_json = json.dumps(rec.get("rules", rec))
                duplicates += 1
            else:
                goal = Goal(
                    goal_code=code,
                    version=int(version),
                    description=rec.get("description"),
                    rules_json=json.dumps(rec.get("rules", rec))
                )
                self.db.add(goal)
            processed += 1

        self.db.commit()
        return IngestionSummary(
            source_file=str(file_path),
            total_records=total,
            processed_records=processed,
            duplicates_detected=duplicates,
            rejected_records=rejected,
            errors=errors
        )

    def ingest_events(self, file_path: Path) -> IngestionSummary:
        records = load_file(file_path)
        total = len(records)
        processed = 0
        rejected = 0
        duplicates = 0
        errors: List[str] = []

        for rec in records:
            if "_error" in rec:
                self._record_rejection("events", str(rec.get("_malformed_raw", rec)), rec["_error"])
                rejected += 1
                errors.append(f"Line {rec.get('_line_no')}: {rec['_error']}")
                continue

            valid, err = validate_raw_event(rec)
            if not valid:
                self._record_rejection("events", json.dumps(rec), err or "Invalid event")
                rejected += 1
                errors.append(err or "Invalid event")
                continue

            source = rec["source"]
            event_type = rec["event_type"]
            event_id = rec.get("event_id")
            v_id_str = rec.get("viewer_id")
            raw_ts = rec.get("timestamp") or rec.get("event_timestamp")

            try:
                event_dt, raw_ts_norm = normalize_timestamp(raw_ts)
            except Exception as e:
                self._record_rejection("events", json.dumps(rec), f"Invalid timestamp: {e}")
                rejected += 1
                errors.append(str(e))
                continue

            dedup_hash = compute_deduplication_hash(
                source=source,
                event_id=event_id,
                event_type=event_type,
                viewer_id=v_id_str,
                raw_timestamp=raw_ts_norm,
                payload=rec
            )

            # Check for existing event by deduplication hash
            existing_evt = self.db.execute(
                select(Event).where(Event.deduplication_hash == dedup_hash)
            ).scalar_one_or_none()

            if existing_evt:
                duplicates += 1
                logger.info(f"Duplicate event detected: {dedup_hash}")
                continue

            # Check if viewer exists or auto-create missing profile
            viewer_internal_id = None
            if v_id_str:
                viewer = self.viewer_service.get_by_viewer_id(v_id_str)
                if not viewer:
                    # Missing viewer profile: create auto profile placeholder
                    viewer = self.viewer_service.create_or_update_viewer(
                        viewer_id=v_id_str,
                        profile_version=1,
                        metadata={"auto_created_from_event": True}
                    )
                viewer_internal_id = viewer.id

            evt = Event(
                event_id=str(event_id) if event_id else None,
                viewer_id=viewer_internal_id,
                source=source,
                event_type=event_type,
                payload_json=json.dumps(rec),
                raw_timestamp=raw_ts_norm,
                event_timestamp=event_dt,
                deduplication_hash=dedup_hash,
                is_duplicate=False
            )
            self.db.add(evt)
            self.db.flush()

            # Extract fact provenance if event contains dialect/language info
            if viewer_internal_id and ("dialect" in rec or "language_variant" in rec):
                self.viewer_service.record_fact(
                    viewer_internal_id=viewer_internal_id,
                    fact_type="event_signal",
                    fact_key="dialect_signal",
                    fact_value=str(rec.get("dialect") or rec.get("language_variant")),
                    evidence_event_id=str(event_id) if event_id else evt.id
                )

            processed += 1

        self.db.commit()
        return IngestionSummary(
            source_file=str(file_path),
            total_records=total,
            processed_records=processed,
            duplicates_detected=duplicates,
            rejected_records=rejected,
            errors=errors
        )

    def ingest_holdouts(self, file_path: Path) -> IngestionSummary:
        records = load_file(file_path)
        total = len(records)
        processed = 0
        rejected = 0
        duplicates = 0
        errors: List[str] = []

        for rec in records:
            v_id = rec.get("viewer_id")
            exp_id = rec.get("experiment_id")
            group = rec.get("group_name", "control")
            if not v_id or not exp_id:
                self._record_rejection("holdouts", str(rec), "Missing viewer_id or experiment_id")
                rejected += 1
                continue

            viewer = self.viewer_service.get_by_viewer_id(v_id)
            if not viewer:
                viewer = self.viewer_service.create_or_update_viewer(viewer_id=v_id)

            existing = self.db.execute(
                select(HoldoutAssignment).where(
                    HoldoutAssignment.viewer_id == viewer.id,
                    HoldoutAssignment.experiment_id == exp_id
                )
            ).scalar_one_or_none()

            if existing:
                existing.group_name = group
                duplicates += 1
            else:
                assign = HoldoutAssignment(
                    viewer_id=viewer.id,
                    experiment_id=exp_id,
                    group_name=group
                )
                self.db.add(assign)
            processed += 1

        self.db.commit()
        return IngestionSummary(
            source_file=str(file_path),
            total_records=total,
            processed_records=processed,
            duplicates_detected=duplicates,
            rejected_records=rejected,
            errors=errors
        )

    def ingest_pilot_data(self, file_path: Path) -> IngestionSummary:
        records = load_file(file_path)
        total = len(records)
        processed = 0
        rejected = 0
        duplicates = 0
        errors: List[str] = []

        for rec in records:
            exp_id = rec.get("experiment_id")
            v_id = rec.get("viewer_id")
            metrics = rec.get("metrics", {})
            if not exp_id or not v_id:
                self._record_rejection("pilot_data", str(rec), "Missing experiment_id or viewer_id")
                rejected += 1
                continue

            viewer = self.viewer_service.get_by_viewer_id(v_id)
            if not viewer:
                viewer = self.viewer_service.create_or_update_viewer(viewer_id=v_id)

            pilot = PilotData(
                experiment_id=exp_id,
                viewer_id=viewer.id,
                metrics_json=json.dumps(metrics)
            )
            self.db.add(pilot)
            processed += 1

        self.db.commit()
        return IngestionSummary(
            source_file=str(file_path),
            total_records=total,
            processed_records=processed,
            duplicates_detected=duplicates,
            rejected_records=rejected,
            errors=errors
        )

    def _record_rejection(self, source: str, raw_data: str, reason: str):
        rejected = RejectedEvent(
            source=source,
            raw_data=raw_data[:2000],
            error_reason=reason
        )
        self.db.add(rejected)
        self.db.commit()
