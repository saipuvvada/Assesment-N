from pathlib import Path
from ott_agent.services.ingestion_service import IngestionService
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.goal_evaluator import GoalEvaluatorService
from ott_agent.models import Goal


def test_goal_eligibility_and_exclusions(db_session):
    """Test goal evaluation, dialect matching, and missing eligibility evidence handling."""
    ing_svc = IngestionService(db_session)
    ing_svc.ingest_goal_rules(Path("./data/fixtures/goal_rules.json"))

    v_svc = ViewerService(db_session)
    v = v_svc.create_or_update_viewer("usr_goal_eval", dialect_preference="Egyptian Arabic", engagement_score=0.8)
    state = v_svc.get_latest_state(v.id)

    eval_svc = GoalEvaluatorService(db_session)
    best_goal, rationale = eval_svc.select_best_goal(v.id, state)

    assert best_goal is not None
    assert best_goal.is_eligible is True
    assert best_goal.goal_code.startswith("DIALECT_RETENTION")
    assert best_goal.deadline_timestamp is not None


def test_unsupported_success_signal_and_underspecified_goals(db_session):
    """Test that goals with unavailable success signals or underspecified rules are excluded."""
    eval_svc = GoalEvaluatorService(db_session)
    v_svc = ViewerService(db_session)

    v = v_svc.create_or_update_viewer("usr_unsupported")
    state = v_svc.get_latest_state(v.id)

    # Goal with unsupported signal
    bad_goal = Goal(
        goal_code="CHURN_PREVENTION",
        version=1,
        description="Prevent churn",
        rules_json='{"success_signal": "churn_risk_score", "min_engagement_threshold": 0.5}'
    )
    db_session.add(bad_goal)
    db_session.commit()

    res = eval_svc.evaluate_goal_for_viewer(bad_goal, v.id, state)
    assert res.is_supported is False
    assert res.is_eligible is False
    assert any("unavailable success signal" in r for r in res.exclusion_reasons)
