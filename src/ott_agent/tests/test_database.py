import os
import tempfile
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ott_agent.database import init_db, Base
from ott_agent.models.viewer import Viewer


def test_database_initialization(test_engine):
    """Test that database tables are created successfully."""
    from sqlalchemy import inspect
    inspector = inspect(test_engine)
    tables = inspector.get_table_names()
    assert "viewers" in tables
    assert "events" in tables
    assert "plans" in tables
    assert "decisions" in tables
    assert "content_items" in tables
    assert "rejected_events" in tables


def test_database_restart_persistence():
    """Test that data written to SQLite persists across engine re-initialization/restart."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db_url = f"sqlite:///{db_path}"
        engine1 = create_engine(db_url, connect_args={"check_same_thread": False})
        init_db(engine1)
        Session1 = sessionmaker(bind=engine1)

        # Insert viewer record
        session1 = Session1()
        v = Viewer(viewer_id="usr_persistent", profile_version=1)
        session1.add(v)
        session1.commit()
        session1.close()
        engine1.dispose()

        # Re-open database with new engine/session
        engine2 = create_engine(db_url, connect_args={"check_same_thread": False})
        init_db(engine2)
        Session2 = sessionmaker(bind=engine2)
        session2 = Session2()

        found = session2.execute(select(Viewer).where(Viewer.viewer_id == "usr_persistent")).scalar_one_or_none()
        assert found is not None
        assert found.viewer_id == "usr_persistent"
        session2.close()
        engine2.dispose()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
