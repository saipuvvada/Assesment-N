import logging
from typing import Generator
from sqlalchemy import create_engine, event, Index, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from ott_agent.config import settings

logger = logging.getLogger(__name__)

# Create engine with connect args for SQLite
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    future=True,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforce foreign key constraints in SQLite on connect."""
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for providing a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """Initialize database tables and active plan partial unique index."""
    eng = target_engine or engine
    # Import all models to ensure they are registered on Base
    import ott_agent.models  # noqa: F401

    Base.metadata.create_all(bind=eng)

    # For SQLite, ensure unique partial index for single active plan per viewer
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_viewer_active_plan
                    ON plans (viewer_id)
                    WHERE plan_status = 'ACTIVE';
                    """
                )
            )
    logger.info("Database initialized successfully.")
