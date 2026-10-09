from ott_agent.routers.health import router as health_router
from ott_agent.routers.viewers import router as viewers_router
from ott_agent.routers.decisions import router as decisions_router
from ott_agent.routers.agent import router as agent_router

__all__ = ["health_router", "viewers_router", "decisions_router", "agent_router"]
