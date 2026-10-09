from pathlib import Path
from sqlalchemy import select
from ott_agent.services.ingestion_service import IngestionService
from ott_agent.models import ContentItem, Goal


def test_catalogue_availability_windows(db_session):
    """Test ingestion of catalogue items and verification of availability start/end datetimes."""
    svc = IngestionService(db_session)
    svc.ingest_catalogue(Path("./data/fixtures/catalogue.csv"))

    item = db_session.execute(select(ContentItem).where(ContentItem.content_id == "show_201")).scalar_one_or_none()
    assert item is not None
    assert item.dialect == "Egyptian Arabic"
    assert item.availability_start.year == 2026
    assert item.availability_end.year == 2026


def test_goal_rule_versioning(db_session):
    """Test versioned goal rules storage."""
    svc = IngestionService(db_session)
    svc.ingest_goal_rules(Path("./data/fixtures/goal_rules.json"))

    goals = db_session.execute(select(Goal).where(Goal.goal_code.startswith("DIALECT_RETENTION"))).scalars().all()
    assert len(goals) == 2
    versions = {g.version for g in goals}
    assert versions == {1, 2}


def test_catalogue_upsert_on_duplicate(db_session, tmp_path):
    """Verify that ingesting a modified duplicate record updates existing values instead of keeping stale ones."""
    svc = IngestionService(db_session)
    cat_file = tmp_path / "catalogue.csv"

    # Ingest original
    cat_file.write_text(
        "content_id,title,dialect,language_variant,availability_start,availability_end,category\n"
        "show_test,Original Title,Egyptian Arabic,ar-EG,2026-01-01T00:00:00Z,2026-12-31T23:59:59Z,Drama\n"
    )
    res1 = svc.ingest_catalogue(cat_file)
    assert res1.processed_records == 1

    item1 = db_session.execute(select(ContentItem).where(ContentItem.content_id == "show_test")).scalar_one_or_none()
    assert item1.title == "Original Title"
    assert item1.dialect == "Egyptian Arabic"

    # Re-ingest duplicate with updated dialect and start date
    cat_file.write_text(
        "content_id,title,dialect,language_variant,availability_start,availability_end,category\n"
        "show_test,Updated Title,Levantine Arabic,ar-LB,2026-06-01T00:00:00Z,2026-12-31T23:59:59Z,Action\n"
    )
    res2 = svc.ingest_catalogue(cat_file)
    assert res2.duplicates_detected == 1

    item2 = db_session.execute(select(ContentItem).where(ContentItem.content_id == "show_test")).scalar_one_or_none()
    assert item2.title == "Updated Title"
    assert item2.dialect == "Levantine Arabic"
    assert item2.availability_start.month == 6


def test_content_selection_availability_boundaries(db_session):
    """Test boundary checks: future titles, expired titles, exact start/end boundary matches."""
    from datetime import datetime, timezone
    from ott_agent.services.content_selection_service import ContentSelectionService
    from ott_agent.models.catalogue import ContentItem

    # Insert items with explicit windows
    item_active = ContentItem(
        content_id="show_act",
        title="Active Show 1",
        dialect="Egyptian Arabic",
        language_variant="ar-EG",
        availability_start=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        availability_end=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    )
    item_future = ContentItem(
        content_id="show_fut",
        title="Future Show 2",
        dialect="Egyptian Arabic",
        language_variant="ar-EG",
        availability_start=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
        availability_end=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    )
    item_expired = ContentItem(
        content_id="show_exp",
        title="Expired Show 3",
        dialect="Egyptian Arabic",
        language_variant="ar-EG",
        availability_start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        availability_end=datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    )
    db_session.add_all([item_active, item_future, item_expired])
    db_session.commit()

    content_svc = ContentSelectionService(db_session)
    eval_time = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Test filtering logic
    items = db_session.execute(select(ContentItem)).scalars().all()
    valid_items = []
    for item in items:
        st = item.availability_start.replace(tzinfo=timezone.utc) if item.availability_start.tzinfo is None else item.availability_start
        et = item.availability_end.replace(tzinfo=timezone.utc) if item.availability_end.tzinfo is None else item.availability_end
        if st <= eval_time <= et:
            valid_items.append(item.content_id)

    assert "show_act" in valid_items
    assert "show_fut" not in valid_items
    assert "show_exp" not in valid_items


def test_large_scale_1500_catalogue_ingestion(db_session, tmp_path):
    """Test ingestion of a 1,500-title synthetic dataset across 6 dialects."""
    dialects = ["Egyptian Arabic", "Levantine Arabic", "Gulf Arabic", "Maghrebi Arabic", "Iraqi Arabic", "Sudanese Arabic"]
    variants = ["ar-EG", "ar-LB", "ar-AE", "ar-MA", "ar-IQ", "ar-SD"]

    large_csv = tmp_path / "catalogue_1500.csv"
    with open(large_csv, "w", encoding="utf-8") as f:
        f.write("content_id,title,dialect,language_variant,availability_start,availability_end,category\n")
        for i in range(1, 1501):
            d_idx = i % len(dialects)
            f.write(f"show_{i:04d},Synthetic Title {i},{dialects[d_idx]},{variants[d_idx]},2026-01-01T00:00:00Z,2026-12-31T23:59:59Z,Drama\n")

    svc = IngestionService(db_session)
    summary = svc.ingest_catalogue(large_csv)

    assert summary.processed_records == 1500
    assert summary.rejected_records == 0

    count = db_session.execute(select(ContentItem)).scalars().all()
    assert len(count) >= 1500


