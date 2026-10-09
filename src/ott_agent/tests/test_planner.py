from pathlib import Path
from ott_agent.services.ingestion_service import IngestionService
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.planner_service import PlannerService
from ott_agent.services.evidence_service import EvidenceService


def test_existing_plan_reuse(db_session):
    """Test that PlannerService reuses an existing valid plan across app open triggers."""
    ing_svc = IngestionService(db_session)
    ing_svc.ingest_goal_rules(Path("./data/fixtures/goal_rules.json"))

    v_svc = ViewerService(db_session)
    v = v_svc.create_or_update_viewer("usr_planner_reuse", dialect_preference="Egyptian Arabic", engagement_score=0.8)
    state = v_svc.get_latest_state(v.id)

    p_svc = PlannerService(db_session)

    # First call creates plan
    plan1, goal_eval1, is_reused1, _ = p_svc.get_or_create_plan(v.id, state)
    assert plan1 is not None
    assert is_reused1 is False

    # Second call reuses existing active plan
    plan2, goal_eval2, is_reused2, _ = p_svc.get_or_create_plan(v.id, state)
    assert plan2.id == plan1.id
    assert is_reused2 is True


def test_purchase_driven_replanning(db_session):
    """Test that a verified purchase event cancels free-tier subscription goal plans."""
    ing_svc = IngestionService(db_session)
    ing_svc.ingest_goal_rules(Path("./data/fixtures/goal_rules.json"))

    v_svc = ViewerService(db_session)
    e_svc = EvidenceService(db_session)
    p_svc = PlannerService(db_session)

    v = v_svc.create_or_update_viewer("usr_purchase_replan", dialect_preference="Egyptian Arabic", engagement_score=0.8)
    e_svc.record_fact(v.id, "subscription", "subscription_status", "FREE", source_type="profile")
    state = v_svc.get_latest_state(v.id)

    plan1, _, _, _ = p_svc.get_or_create_plan(v.id, state)
    assert plan1.plan_status == "ACTIVE"

    # User completes verified purchase event
    e_svc.record_fact(v.id, "subscription", "subscription_status", "SUBSCRIBED", source_type="purchase_event")
    updated_state = v_svc.get_latest_state(v.id)

    # Trigger planner -> active plan for free tier should be cancelled
    plan2, _, _, _ = p_svc.get_or_create_plan(v.id, updated_state)
    db_session.refresh(plan1)

    assert plan1.plan_status == "CANCELLED"
