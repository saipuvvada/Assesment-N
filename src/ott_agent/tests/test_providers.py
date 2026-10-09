import pytest
from ott_agent.providers.base import BaseModelProvider, ProviderBudgetConfig
from ott_agent.providers.mock_provider import RuleBasedModelProvider
from ott_agent.providers.hosted_provider import HostedModelProvider


class FailingModelProvider(BaseModelProvider):
    def _generate_decision_raw(self, viewer_id, viewer_state, available_catalogue, goal_rules):
        raise RuntimeError("Simulated hosted model failure")


def test_model_budget_enforcement_max_calls():
    """Test that model call budget enforcement triggers fallback when exceeded."""
    config = ProviderBudgetConfig(max_model_calls=2, max_retries=0)
    provider = RuleBasedModelProvider(budget_config=config)

    res1 = provider.generate_decision("usr_b1", {"dialect_preference": "Egyptian Arabic"}, [], [])
    assert res1.get("fallback_used") is False

    res2 = provider.generate_decision("usr_b1", {"dialect_preference": "Egyptian Arabic"}, [], [])
    assert res2.get("fallback_used") is False

    # 3rd call exceeds max_model_calls (2)
    res3 = provider.generate_decision("usr_b1", {"dialect_preference": "Egyptian Arabic"}, [], [])
    assert res3.get("fallback_used") is True
    assert "Model call limit exceeded" in provider.metrics.fallback_reason


def test_provider_exception_fallback_to_mock():
    """Test that provider exceptions automatically trigger fallback to mock mode."""
    config = ProviderBudgetConfig(max_retries=1)
    provider = FailingModelProvider(budget_config=config)

    res = provider.generate_decision("usr_fail", {"dialect_preference": "Levantine Arabic"}, [], [])
    assert res.get("fallback_used") is True
    assert provider.metrics.fallback_triggered is True
    assert "Simulated hosted model failure" in provider.metrics.fallback_reason


def test_hosted_provider_without_api_key_fallbacks():
    """Test that HostedModelProvider without API key gracefully falls back."""
    provider = HostedModelProvider(api_key=None)
    res = provider.generate_decision("usr_hosted", {"dialect_preference": "Egyptian Arabic"}, [], [])
    assert res.get("fallback_used") is True
