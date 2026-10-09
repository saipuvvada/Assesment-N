import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
import typer
from sqlalchemy import select, func

from ott_agent.database import init_db, SessionLocal, engine
from ott_agent.services.ingestion_service import IngestionService
from ott_agent.services.agent_service import ViewerAgentService
from ott_agent.services.replay_runner import ReplayRunnerService
from ott_agent.models import Viewer, Event, RejectedEvent, ContentItem, Goal, Plan, Decision, Action, Outcome

app = typer.Typer(help="CLI tool for OTT Dialect Platform - Data Ingestion, Replay, Agent Execution, and Management.")
logger = logging.getLogger(__name__)


@app.command()
def init():
    """Initialize database schema and indices."""
    typer.echo("Initializing database tables and active plan indices...")
    init_db(engine)
    typer.echo("Database initialized successfully.")


@app.command()
def ingest(
    viewers: Optional[Path] = typer.Option(None, help="Path to viewers profile JSON/CSV file"),
    catalogue: Optional[Path] = typer.Option(None, help="Path to catalogue CSV/JSON file"),
    goal_rules: Optional[Path] = typer.Option(None, help="Path to goal rules JSON file"),
    events: Optional[Path] = typer.Option(None, help="Path to events JSONL/JSON file"),
    holdouts: Optional[Path] = typer.Option(None, help="Path to holdouts CSV file"),
    pilot_data: Optional[Path] = typer.Option(None, help="Path to pilot data JSON file"),
    all_fixtures: bool = typer.Option(False, "--all", help="Ingest all mock fixtures from data/fixtures/")
):
    """Ingest datasets into the database."""
    init_db(engine)
    db = SessionLocal()
    svc = IngestionService(db)

    try:
        if all_fixtures:
            fixture_dir = Path("./data/fixtures")
            if (fixture_dir / "viewers.json").exists():
                viewers = fixture_dir / "viewers.json"
            if (fixture_dir / "catalogue.csv").exists():
                catalogue = fixture_dir / "catalogue.csv"
            if (fixture_dir / "goal_rules.json").exists():
                goal_rules = fixture_dir / "goal_rules.json"
            if (fixture_dir / "events.jsonl").exists():
                events = fixture_dir / "events.jsonl"
            if (fixture_dir / "holdouts.csv").exists():
                holdouts = fixture_dir / "holdouts.csv"
            if (fixture_dir / "pilot_data.json").exists():
                pilot_data = fixture_dir / "pilot_data.json"

        if viewers:
            typer.echo(f"Ingesting viewers from {viewers}...")
            res = svc.ingest_viewers(viewers)
            typer.echo(f"  Result: {res.processed_records} processed, {res.rejected_records} rejected.")

        if catalogue:
            typer.echo(f"Ingesting catalogue from {catalogue}...")
            res = svc.ingest_catalogue(catalogue)
            typer.echo(f"  Result: {res.processed_records} processed, {res.rejected_records} rejected.")

        if goal_rules:
            typer.echo(f"Ingesting goal rules from {goal_rules}...")
            res = svc.ingest_goal_rules(goal_rules)
            typer.echo(f"  Result: {res.processed_records} processed, {res.rejected_records} rejected.")

        if events:
            typer.echo(f"Ingesting events from {events}...")
            res = svc.ingest_events(events)
            typer.echo(f"  Result: {res.processed_records} processed, {res.duplicates_detected} duplicates, {res.rejected_records} rejected.")

        if holdouts:
            typer.echo(f"Ingesting holdouts from {holdouts}...")
            res = svc.ingest_holdouts(holdouts)
            typer.echo(f"  Result: {res.processed_records} processed, {res.rejected_records} rejected.")

        if pilot_data:
            typer.echo(f"Ingesting pilot data from {pilot_data}...")
            res = svc.ingest_pilot_data(pilot_data)
            typer.echo(f"  Result: {res.processed_records} processed, {res.rejected_records} rejected.")

    finally:
        db.close()


@app.command()
def trigger(viewer_id: str = typer.Argument(..., help="Viewer ID to trigger agent decision for")):
    """Trigger Per-Viewer Agent decision run for a viewer."""
    init_db(engine)
    db = SessionLocal()
    agent = ViewerAgentService(db)
    try:
        res = agent.process_app_open_trigger(viewer_id=viewer_id)
        typer.echo(json.dumps(res, indent=2))
    finally:
        db.close()


@app.command()
def replay(
    input_file: Path = typer.Option(Path("data/fixtures/events.jsonl"), "--input", "-i", help="Input trigger/event file"),
    output: Path = typer.Option(Path("sample_run"), "--output", "-o", help="Output directory for sample run artifacts"),
    seed: int = typer.Option(42, "--seed", help="Random seed for simulation"),
    run_id: str = typer.Option("run_default", "--run-id", help="Replay run identifier"),
    fresh: bool = typer.Option(False, "--fresh", help="Run fresh replay from beginning ignoring previous checkpoints")
):
    """Run event replay and generate sample run artifacts (decisions.jsonl, actions.jsonl, outcomes.jsonl, latency_report.json, impact_report.md, final_report.md)."""
    init_db(engine)
    db = SessionLocal()
    actual_run_id = f"{run_id}_{int(datetime.now().timestamp())}" if fresh else run_id
    runner = ReplayRunnerService(db, run_id=actual_run_id)
    try:
        res = runner.run_replay(input_file=input_file, output_dir=output, deterministic_seed=seed)
        typer.echo(f"Replay completed successfully. Artifacts saved in '{output}' directory.")
        typer.echo(json.dumps(res, indent=2))
    finally:
        db.close()


@app.command()
def export_decisions(output: Path = typer.Option(Path("decisions.jsonl"), help="Output JSONL filepath")):
    """Export all persisted decisions to a JSONL file."""
    db = SessionLocal()
    agent = ViewerAgentService(db)
    try:
        decisions = db.execute(select(Decision)).scalars().all()
        count = 0
        with open(output, "w", encoding="utf-8") as f:
            for d in decisions:
                ext_id = d.viewer.viewer_id if d.viewer else d.viewer_id
                payload = agent._build_audit_payload(d, ext_id)
                f.write(json.dumps(payload) + "\n")
                count += 1
        typer.echo(f"Exported {count} decisions to {output}")
    finally:
        db.close()


@app.command()
def status():
    """Display current database record counts and status summary."""
    db = SessionLocal()
    try:
        n_viewers = db.execute(select(func.count(Viewer.id))).scalar()
        n_events = db.execute(select(func.count(Event.id))).scalar()
        n_rejected = db.execute(select(func.count(RejectedEvent.id))).scalar()
        n_catalogue = db.execute(select(func.count(ContentItem.id))).scalar()
        n_goals = db.execute(select(func.count(Goal.id))).scalar()
        n_plans = db.execute(select(func.count(Plan.id))).scalar()
        n_active_plans = db.execute(select(func.count(Plan.id)).where(Plan.plan_status == "ACTIVE")).scalar()
        n_decisions = db.execute(select(func.count(Decision.id))).scalar()
        n_actions = db.execute(select(func.count(Action.id))).scalar()
        n_outcomes = db.execute(select(func.count(Outcome.id))).scalar()

        typer.echo("================ OTT PLATFORM STATUS ================")
        typer.echo(f"Viewers:           {n_viewers}")
        typer.echo(f"Catalogue Items:   {n_catalogue}")
        typer.echo(f"Goals:             {n_goals}")
        typer.echo(f"Events Ingested:   {n_events}")
        typer.echo(f"Rejected Events:   {n_rejected}")
        typer.echo(f"Total Plans:       {n_plans} ({n_active_plans} ACTIVE)")
        typer.echo(f"Decisions:         {n_decisions}")
        typer.echo(f"Actions Executed:  {n_actions}")
        typer.echo(f"Outcomes Assessed: {n_outcomes}")
        typer.echo("====================================================")
    finally:
        db.close()


if __name__ == "__main__":
    app()
