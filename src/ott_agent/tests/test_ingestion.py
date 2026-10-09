from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select
from ott_agent.services.ingestion_service import IngestionService
from ott_agent.models import Event, RejectedEvent
from ott_agent.ingestion.normalizer import normalize_timestamp, compute_deduplication_hash


def test_timestamp_normalization():
    """Test ISO 8601, UTC offset, and timestamp string parsing."""
    dt1, raw1 = normalize_timestamp("2026-03-01T14:00:00Z")
    assert dt1.tzinfo == timezone.utc
    assert dt1.hour == 14

    # Timestamp with +02:00 offset should normalize to 12:00 UTC
    dt2, raw2 = normalize_timestamp("2026-03-01T14:00:00+02:00")
    assert dt2.tzinfo == timezone.utc
    assert dt2.hour == 12
    assert raw2 == "2026-03-01T14:00:00+02:00"


def test_ingestion_valid_and_malformed_records(db_session):
    """Test ingesting events fixture with valid, duplicate, and malformed records."""
    svc = IngestionService(db_session)
    fixture_file = Path("./data/fixtures/events.jsonl")

    res = svc.ingest_events(fixture_file)
    assert res.total_records == 7
    assert res.processed_records == 5
    assert res.duplicates_detected == 1
    assert res.rejected_records == 1

    # Check rejected events table
    rejected = db_session.execute(select(RejectedEvent)).scalars().all()
    assert len(rejected) == 1
    assert "events" in rejected[0].source


def test_duplicate_ingestion_idempotency(db_session):
    """Test that running ingestion twice produces 0 new records and registers duplicates."""
    svc = IngestionService(db_session)
    fixture_file = Path("./data/fixtures/events.jsonl")

    res1 = svc.ingest_events(fixture_file)
    count_before = len(db_session.execute(select(Event)).scalars().all())

    res2 = svc.ingest_events(fixture_file)
    count_after = len(db_session.execute(select(Event)).scalars().all())

    assert res2.processed_records == 0
    assert res2.duplicates_detected == 6
    assert count_before == count_after
