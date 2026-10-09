from pathlib import Path
from ott_agent.services.ingestion_service import IngestionService
from ott_agent.services.decision_service import DecisionService
from ott_agent.services.viewer_service import ViewerService


def test_health_endpoints(client):
    """Test health and readiness endpoints."""
    r1 = client.get("/health")
    assert r1.status_code == 200
    assert r1.json()["status"] == "healthy"

    r2 = client.get("/health/ready")
    assert r2.status_code == 200
    assert r2.json()["database"] == "connected"


def test_viewer_api_endpoints(client, db_session):
    """Test viewer profile, state, and decision endpoints."""
    svc = IngestionService(db_session)
    svc.ingest_viewers(Path("./data/fixtures/viewers.json"))

    # Test non-existent viewer
    r_404 = client.get("/viewers/non_existent_usr")
    assert r_404.status_code == 404

    # Test valid viewer profile
    r_profile = client.get("/viewers/usr_1001")
    assert r_profile.status_code == 200
    data = r_profile.json()
    assert data["viewer_id"] == "usr_1001"
    assert data["profile_version"] == 1
    assert data["current_state"]["dialect_preference"] == "Egyptian Arabic"

    # Test viewer state endpoint
    r_state = client.get("/viewers/usr_1001/state")
    assert r_state.status_code == 200
    assert r_state.json()["dialect_preference"] == "Egyptian Arabic"


def test_decision_api_endpoints(client, db_session):
    """Test decisions endpoints."""
    v_svc = ViewerService(db_session)
    d_svc = DecisionService(db_session)

    viewer = v_svc.create_or_update_viewer("usr_api_dec")
    decision = d_svc.record_decision(
        viewer_internal_id=viewer.id,
        decision_type="TEST_RECOMMENDATION",
        recommended_action="RECOMMEND_SHOW:show_201",
        rationale="Test recommendation rationale",
        evidence_refs=["evt_001"]
    )

    # Test viewer decisions list
    r_list = client.get("/viewers/usr_api_dec/decisions")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    # Test decision detail by ID
    r_detail = client.get(f"/decisions/{decision.id}")
    assert r_detail.status_code == 200
    assert r_detail.json()["recommended_action"] == "RECOMMEND_SHOW:show_201"
    assert r_detail.json()["evidence_refs"] == ["evt_001"]

    # Test 404 for invalid decision ID
    r_bad_dec = client.get("/decisions/invalid_id")
    assert r_bad_dec.status_code == 404
