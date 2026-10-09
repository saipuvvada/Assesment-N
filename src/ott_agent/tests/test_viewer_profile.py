from sqlalchemy import select
from ott_agent.services.viewer_service import ViewerService
from ott_agent.models import Viewer, ViewerState


def test_create_and_update_viewer_profile(db_session):
    """Test viewer profile creation and version updates."""
    svc = ViewerService(db_session)

    # Initial profile v1
    v1 = svc.create_or_update_viewer(
        viewer_id="usr_test_101",
        profile_version=1,
        dialect_preference="Egyptian Arabic",
        engagement_score=0.7
    )
    assert v1.profile_version == 1

    # Update with v2
    v2 = svc.create_or_update_viewer(
        viewer_id="usr_test_101",
        profile_version=2,
        dialect_preference="Levantine Arabic",
        engagement_score=0.9
    )
    assert v2.profile_version == 2

    # Check state history
    states = db_session.execute(select(ViewerState).where(ViewerState.viewer_id == v1.id)).scalars().all()
    assert len(states) == 2


def test_conflicting_older_profile_version(db_session):
    """Test that an older incoming profile version (v1) does not downgrade existing profile version (v2)."""
    svc = ViewerService(db_session)

    # Create v2
    svc.create_or_update_viewer(viewer_id="usr_conflict", profile_version=2)

    # Incoming conflict with v1
    v_updated = svc.create_or_update_viewer(viewer_id="usr_conflict", profile_version=1)
    assert v_updated.profile_version == 2
