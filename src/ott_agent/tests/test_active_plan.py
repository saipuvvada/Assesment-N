import pytest
from sqlalchemy.exc import IntegrityError
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.plan_service import PlanService
from ott_agent.models import Goal, Plan


def test_single_active_plan_service_deactivation(db_session):
    """Test that PlanService automatically deactivates previous active plan when replacing."""
    v_svc = ViewerService(db_session)
    p_svc = PlanService(db_session)

    v = v_svc.create_or_update_viewer("usr_plan_test")
    goal1 = Goal(goal_code="GOAL_1", version=1, rules_json="{}")
    goal2 = Goal(goal_code="GOAL_2", version=1, rules_json="{}")
    db_session.add_all([goal1, goal2])
    db_session.commit()

    plan1 = p_svc.create_plan(v.id, goal1.id, steps=["step1"])
    assert plan1.plan_status == "ACTIVE"

    # Creating second plan with replace_existing=True
    plan2 = p_svc.create_plan(v.id, goal2.id, steps=["step2"], replace_existing=True)
    db_session.refresh(plan1)

    assert plan1.plan_status == "CANCELLED"
    assert plan2.plan_status == "ACTIVE"
    assert p_svc.get_active_plan(v.id).id == plan2.id


def test_sqlite_unique_active_plan_constraint_rollback(db_session):
    """Test that SQLite unique partial index prevents concurrent active plans and forces transaction rollback."""
    v_svc = ViewerService(db_session)
    v = v_svc.create_or_update_viewer("usr_plan_concurrent")
    goal = Goal(goal_code="GOAL_LOCK", version=1, rules_json="{}")
    db_session.add(goal)
    db_session.commit()

    p1 = Plan(viewer_id=v.id, goal_id=goal.id, plan_status="ACTIVE", steps_json="[]")
    db_session.add(p1)
    db_session.commit()

    # Attempt to insert a second ACTIVE plan for the same viewer without deactivating p1
    p2 = Plan(viewer_id=v.id, goal_id=goal.id, plan_status="ACTIVE", steps_json="[]")
    db_session.add(p2)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
    active = db_session.query(Plan).filter(Plan.viewer_id == v.id, Plan.plan_status == "ACTIVE").all()
    assert len(active) == 1
