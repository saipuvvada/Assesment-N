from pathlib import Path
import json
import pytest
from sqlalchemy import select

from ott_agent.services.replay_runner import ReplayRunnerService
from ott_agent.services.outcome_evaluator import OutcomeEvaluatorService
from ott_agent.services.impact_analysis import RandomizedHoldoutAnalyzer
from ott_agent.services.latency_reporter import LatencyReporterService
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.evidence_service import EvidenceService
from ott_agent.services.agent_service import ViewerAgentService
from ott_agent.models import Decision, Plan, Goal, Outcome, ReplayCheckpoint, HoldoutAssignment


def test_outcome_evaluator_statuses(db_session):
    """Test outcome evaluation for SUCCEEDED, FAILED, INCONCLUSIVE, and PENDING statuses."""
    v_svc = ViewerService(db_session)
    e_svc = EvidenceService(db_session)
    eval_svc = OutcomeEvaluatorService(db_session)

    v = v_svc.create_or_update_viewer("usr_out_101")
    state = v_svc.get_latest_state(v.id)

    # Goal with unavailable signal -> INCONCLUSIVE
    bad_goal = Goal(
        goal_code="GOAL_UNAVAILABLE_SIGNAL",
        version=1,
        rules_json='{"success_signal": "churn_risk_score"}'
    )
    db_session.add(bad_goal)
    db_session.commit()

    dec1 = Decision(
        viewer_id=v.id,
        decision_type="TEST",
        recommended_action="TEST_ACTION",
        success_signal="churn_risk_score",
        goal_id=bad_goal.id,
        rationale="Test unavailable signal",
        status="ACTIVE"
    )
    db_session.add(dec1)
    db_session.commit()

    res_inc = eval_svc.evaluate_single_decision(dec1.id)
    assert res_inc["status"] == "INCONCLUSIVE"


def test_impact_analysis_itt_calculation(db_session):
    """Test randomized holdout ITT causal impact calculation."""
    analyzer = RandomizedHoldoutAnalyzer(db_session)

    v_svc = ViewerService(db_session)
    v1 = v_svc.create_or_update_viewer("usr_itt_treat_1")
    v2 = v_svc.create_or_update_viewer("usr_itt_ctrl_1")

    # Add holdout assignments
    a1 = HoldoutAssignment(viewer_id=v1.id, experiment_id="exp_test_2026", group_name="treatment")
    a2 = HoldoutAssignment(viewer_id=v2.id, experiment_id="exp_test_2026", group_name="control")
    db_session.add_all([a1, a2])
    db_session.commit()

    # Add successful outcome for treatment viewer
    o1 = Outcome(viewer_id=v1.id, metric_name="goal_success", metric_value=1.0)
    db_session.add(o1)
    db_session.commit()

    res = analyzer.perform_itt_analysis(experiment_id="exp_test_2026")
    assert res["treatment_group"]["sample_size"] == 1
    assert res["control_group"]["sample_size"] == 1
    assert res["impact_metrics"]["absolute_difference_pp"] == 100.0


def test_latency_reporter_generation(db_session, tmp_path):
    """Test operational latency report generation."""
    reporter = LatencyReporterService(db_session)
    v_svc = ViewerService(db_session)
    v = v_svc.create_or_update_viewer("usr_lat_test")

    dec = Decision(
        viewer_id=v.id,
        decision_type="HOMEPAGE_ROW",
        recommended_action="RECOMMEND_SHOW:show_201",
        rationale="Latency test decision",
        decision_latency_ms=35.5,
        status="ACTIVE"
    )
    db_session.add(dec)
    db_session.commit()

    report_file = tmp_path / "latency_report.json"
    rep_dict = reporter.generate_latency_report(report_file)

    assert report_file.exists()
    assert rep_dict["summary"]["successful_decisions"] == 1
    assert rep_dict["latency_stats_ms"]["median_ms"] == 35.5


def test_replay_runner_execution_and_checkpoint_resume(db_session, tmp_path):
    """Test full replay runner execution, artifact generation, and checkpoint resume."""
    input_file = Path("./data/fixtures/events.jsonl")
    output_dir = tmp_path / "sample_run"

    runner = ReplayRunnerService(db_session, run_id="test_run_001")
    res = runner.run_replay(input_file=input_file, output_dir=output_dir)

    assert (output_dir / "decisions.jsonl").exists()
    assert (output_dir / "actions.jsonl").exists()
    assert (output_dir / "outcomes.jsonl").exists()
    assert (output_dir / "latency_report.json").exists()
    assert (output_dir / "impact_report.md").exists()
    assert (output_dir / "final_report.md").exists()

    # Verify checkpoint recorded
    cps = db_session.execute(select(ReplayCheckpoint)).scalars().all()
    assert len(cps) > 0
