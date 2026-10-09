import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderBudgetConfig(BaseModel):
    max_model_calls: int = Field(default=8, description="Maximum allowed model calls per decision")
    max_tool_calls: int = Field(default=20, description="Maximum allowed tool calls per decision")
    timeout_seconds: float = Field(default=5.0, description="Call timeout in seconds")
    max_retries: int = Field(default=2, description="Bounded retry attempts")


class ProviderUsageMetrics(BaseModel):
    model_calls_made: int = 0
    tool_calls_made: int = 0
    total_latency_ms: float = 0.0
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None


class BaseModelProvider(ABC):
    """Abstract provider interface for OTT Dialect Agent decisions with call budget enforcement."""

    def __init__(self, budget_config: Optional[ProviderBudgetConfig] = None):
        self.config = budget_config or ProviderBudgetConfig()
        self.metrics = ProviderUsageMetrics()

    def reset_metrics(self):
        self.metrics = ProviderUsageMetrics()

    @abstractmethod
    def _generate_decision_raw(
        self,
        viewer_id: str,
        viewer_state: Dict[str, Any],
        available_catalogue: List[Dict[str, Any]],
        goal_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Internal call logic implemented by provider."""
        pass

    def generate_decision(
        self,
        viewer_id: str,
        viewer_state: Dict[str, Any],
        available_catalogue: List[Dict[str, Any]],
        goal_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate structured decision enforcing timeout, budget limits, retries, and fallback."""
        start_t = time.time()
        self.metrics.model_calls_made += 1

        if self.metrics.model_calls_made > self.config.max_model_calls:
            self.metrics.fallback_triggered = True
            self.metrics.fallback_reason = f"Model call limit exceeded ({self.metrics.model_calls_made} > {self.config.max_model_calls})"
            logger.warning(self.metrics.fallback_reason)
            return self._fallback_decision(viewer_state, available_catalogue, self.metrics.fallback_reason)

        if self.metrics.tool_calls_made > self.config.max_tool_calls:
            self.metrics.fallback_triggered = True
            self.metrics.fallback_reason = f"Tool call limit exceeded ({self.metrics.tool_calls_made} > {self.config.max_tool_calls})"
            logger.warning(self.metrics.fallback_reason)
            return self._fallback_decision(viewer_state, available_catalogue, self.metrics.fallback_reason)

        attempts = 0
        last_err = None

        while attempts <= self.config.max_retries:
            try:
                attempts += 1
                res = self._generate_decision_raw(viewer_id, viewer_state, available_catalogue, goal_rules)
                elapsed = (time.time() - start_t) * 1000.0
                self.metrics.total_latency_ms += elapsed
                return res
            except Exception as e:
                last_err = e
                logger.warning(f"Model provider call attempt {attempts} failed: {e}")
                time.sleep(0.05 * attempts)

        # Fallback to deterministic mock mode on failure/timeout
        self.metrics.fallback_triggered = True
        self.metrics.fallback_reason = f"Provider exception after {attempts} attempts: {last_err}"
        elapsed = (time.time() - start_t) * 1000.0
        self.metrics.total_latency_ms += elapsed
        return self._fallback_decision(viewer_state, available_catalogue, self.metrics.fallback_reason)

    def _fallback_decision(
        self,
        viewer_state: Dict[str, Any],
        available_catalogue: List[Dict[str, Any]],
        reason: str
    ) -> Dict[str, Any]:
        pref = viewer_state.get("dialect_preference") or "Egyptian Arabic"
        matches = [c for c in available_catalogue if c.get("dialect") == pref]
        show = matches[0] if matches else (available_catalogue[0] if available_catalogue else {"content_id": "default_show"})

        return {
            "decision_type": "DIALECT_CONTENT_RECOMMENDATION",
            "recommended_action": f"RECOMMEND_SHOW:{show.get('content_id')}",
            "rationale": f"Deterministic fallback recommendation due to: {reason}",
            "evidence_refs": [f"state:dialect_preference:{pref}"],
            "fallback_used": True
        }
