import os
import logging
from typing import Dict, Any, List, Optional
from ott_agent.providers.base import BaseModelProvider

logger = logging.getLogger(__name__)


class HostedModelProvider(BaseModelProvider):
    """Hosted model provider simulation / implementation with automatic fallback to mock mode."""

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv("HOSTED_MODEL_API_KEY")

    def _generate_decision_raw(
        self,
        viewer_id: str,
        viewer_state: Dict[str, Any],
        available_catalogue: List[Dict[str, Any]],
        goal_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("No API key provided for HostedModelProvider; fallback required.")

        preferred_dialect = viewer_state.get("dialect_preference") or "Egyptian Arabic"
        matches = [c for c in available_catalogue if c.get("dialect") == preferred_dialect]
        show = matches[0] if matches else (available_catalogue[0] if available_catalogue else {"content_id": "show_201"})

        return {
            "decision_type": "HOSTED_MODEL_RECOMMENDATION",
            "recommended_action": f"RECOMMEND_SHOW:{show.get('content_id')}",
            "rationale": f"Hosted model recommended show '{show.get('title')}' for viewer {viewer_id}.",
            "evidence_refs": [f"hosted_model_eval:{viewer_id}"],
            "fallback_used": False
        }
