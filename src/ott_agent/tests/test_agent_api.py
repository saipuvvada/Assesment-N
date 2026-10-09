from pathlib import Path
from ott_agent.services.ingestion_service import IngestionService
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.evidence_service import EvidenceService


def test_agent_trigger_and_audit_endpoints(client, db_session):
    """Test POST /agent/trigger and audit record endpoints."""
    ing_svc = IngestionService(db_session)
    ing_svc.ingest_goal_rules(Path("./data/fixtures/goal_rules.json"))
    ing_svc.ingest_catalogue(Path("./data/fixtures/catalogue.csv"))

    v_svc = ViewerService(db_session)
    v = v_svc.create_or_update_viewer("usr_agent_api", dialect_preference="Egyptian Arabic", engagement_score=0.8)

    # 1. Trigger agent
    r_trig = client.post("/agent/trigger", json={"viewer_id": "usr_agent_api", "trigger_event_id": "evt_trigger_100"})
    assert r_trig.status_code == 200
    data = r_trig.json()

    assert data["viewer_id"] == "usr_agent_api"
    assert "decision_id" in data
    assert data["status"] == "ACTIVE"
    assert data["dialect_selection"]["selected_dialect"] == "Egyptian Arabic"
    assert len(data["content_references"]) > 0

    dec_id = data["decision_id"]

    # 2. Get goal-plan
    r_gp = client.get("/viewers/usr_agent_api/goal-plan")
    assert r_gp.status_code == 200
    assert r_gp.json()["has_active_plan"] is True

    # 3. Get evidence details
    r_ev = client.get("/viewers/usr_agent_api/evidence")
    assert r_ev.status_code == 200
    assert "effective_facts" in r_ev.json()

    # 4. Get decision audit trail
    r_audit = client.get(f"/decisions/{dec_id}/audit")
    assert r_audit.status_code == 200
    assert r_audit.json()["decision_id"] == dec_id


def test_abstention_no_action_decision(client, db_session):
    """Test that agent produces an explicit ABSTAINED decision when no goal is eligible."""
    v_svc = ViewerService(db_session)
    # Low engagement score -> no goal eligible
    v_svc.create_or_update_viewer("usr_abstain", dialect_preference="Egyptian Arabic", engagement_score=0.1)

    r_trig = client.post("/agent/trigger", json={"viewer_id": "usr_abstain"})
    assert r_trig.status_code == 200
    data = r_trig.json()
    assert data["status"] == "ABSTAINED"
    assert data["proposed_action"] == "ABSTAIN"
    assert data["abstention_reason"] is not None
