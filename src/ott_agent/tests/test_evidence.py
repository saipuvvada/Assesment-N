from datetime import datetime, timezone, timedelta
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.evidence_service import EvidenceService, utc_now


def test_conflicting_dialect_sources_precedence(db_session):
    """Test that app_settings precedence overrides profile default preference."""
    v_svc = ViewerService(db_session)
    e_svc = EvidenceService(db_session)

    v = v_svc.create_or_update_viewer("usr_ev_101", dialect_preference="Egyptian Arabic")

    # Profile fact (precedence 40)
    e_svc.record_fact(v.id, "dialect", "dialect_preference", "Egyptian Arabic", source_type="profile")

    # App settings fact (precedence 100)
    e_svc.record_fact(v.id, "dialect", "dialect_preference", "Levantine Arabic", source_type="app_settings")

    eff_val, eff_src, has_conflict, hist = e_svc.resolve_effective_fact(v.id, "dialect_preference")
    assert eff_val == "Levantine Arabic"
    assert eff_src == "app_settings"


def test_stale_profile_vs_purchase_event(db_session):
    """Test that purchase event overrides stale FREE subscription status in profile."""
    v_svc = ViewerService(db_session)
    e_svc = EvidenceService(db_session)

    v = v_svc.create_or_update_viewer("usr_sub_202")

    # Profile says FREE (precedence 30)
    e_svc.record_fact(v.id, "subscription", "subscription_status", "FREE", source_type="profile")

    # Purchase event says SUBSCRIBED (precedence 100)
    e_svc.record_fact(v.id, "subscription", "subscription_status", "SUBSCRIBED", source_type="purchase_event")

    eff_val, eff_src, _, _ = e_svc.resolve_effective_fact(v.id, "subscription_status")
    assert eff_val == "SUBSCRIBED"
    assert eff_src == "purchase_event"


def test_late_event_freshness_rule(db_session):
    """Test that late out-of-order events do not overwrite newer facts."""
    v_svc = ViewerService(db_session)
    e_svc = EvidenceService(db_session)

    v = v_svc.create_or_update_viewer("usr_late_303")
    now = utc_now()
    old_time = now - timedelta(days=5)

    # Newer fact
    e_svc.record_fact(v.id, "dialect", "dialect_preference", "Gulf Arabic", source_type="watch_start", observation_time=now)

    # Out-of-order late event from 5 days ago
    late_fact = e_svc.record_fact(v.id, "dialect", "dialect_preference", "Egyptian Arabic", source_type="watch_start", observation_time=old_time)

    assert late_fact.has_conflict is True
    assert late_fact.resolution_rule == "LATE_EVENT_STALE_RULE"

    eff_val, _, _, _ = e_svc.resolve_effective_fact(v.id, "dialect_preference")
    assert eff_val == "Gulf Arabic"
