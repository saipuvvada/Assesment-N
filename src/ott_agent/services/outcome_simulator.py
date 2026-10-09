import random
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class LocalOutcomeSimulator:
    """Local outcome simulator for deterministic replay evaluation."""

    def __init__(self, seed: Optional[int] = 42):
        self.seed = seed
        if seed is not None:
            random.seed(seed)

    def simulate_outcome(self, viewer_id: str, action_type: str, content_id: str) -> Dict[str, Any]:
        """Simulate a deterministic viewer response outcome based on action type."""
        if action_type == "NO_ACTION":
            return {"outcome": "NO_RESPONSE", "converted": False, "score": 0.0}

        # Deterministic simulation based on viewer_id hash
        val = (hash(f"{viewer_id}:{content_id}") % 100) / 100.0
        converted = val > 0.3

        return {
            "outcome": "WATCH_COMPLETED" if converted else "ABANDONED",
            "converted": converted,
            "score": round(val, 2)
        }
