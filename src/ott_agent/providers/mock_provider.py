from typing import Dict, Any, List
from ott_agent.providers.base import BaseModelProvider


class RuleBasedModelProvider(BaseModelProvider):
    """Deterministic local mock model provider for OTT Dialect Agent decisions."""

    def _generate_decision_raw(
        self,
        viewer_id: str,
        viewer_state: Dict[str, Any],
        available_catalogue: List[Dict[str, Any]],
        goal_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        preferred_dialect = viewer_state.get("dialect_preference") or "Egyptian Arabic"

        matching_content = [
            item for item in available_catalogue
            if item.get("dialect") == preferred_dialect
        ]

        if not matching_content:
            matching_content = available_catalogue

        recommended = matching_content[0] if matching_content else {"content_id": "show_201", "title": "Default Nile Drama"}

        return {
            "decision_type": "DIALECT_CONTENT_RECOMMENDATION",
            "recommended_action": f"RECOMMEND_SHOW:{recommended.get('content_id')}",
            "rationale": f"Selected show '{recommended.get('title')}' matching viewer preferred dialect '{preferred_dialect}'.",
            "evidence_refs": [
                f"state:dialect_preference:{preferred_dialect}",
                f"catalogue:{recommended.get('content_id')}"
            ],
            "fallback_used": False
        }
