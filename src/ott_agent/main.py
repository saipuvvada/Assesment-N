import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ott_agent.config import settings
from ott_agent.database import init_db
from ott_agent.routers import health_router, viewers_router, decisions_router, agent_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ott_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database initialization on startup."""
    logger.info("Initializing OTT Dialect Platform API...")
    init_db()
    yield
    logger.info("Shutting down OTT Dialect Platform API.")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0",
    description="One User, One Agent OTT Dialect Platform API - Phase 2",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(viewers_router)
app.include_router(decisions_router)
app.include_router(agent_router)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to OTT Dialect Platform API (Phase 2)",
        "docs_url": "/docs",
        "health_url": "/health"
    }
