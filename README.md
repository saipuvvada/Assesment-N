# OTT Dialect Platform — One User, One Agent (Complete 4-Phase System)

A production-minded, agentic OTT Dialect Platform built with Python 3.12, FastAPI, SQLAlchemy 2.x, SQLite, Pydantic v2, Typer CLI, and pytest.

---

## Complete 4-Phase Architecture

- **Phase 1: Foundation & Data Ingestion**: Idempotent parsing (CSV, JSON, JSONL), UTC timestamp normalization, duplicate detection, malformed record handling (`rejected_events`), evidence provenance, and SQLite single active plan schema constraint.
- **Phase 2: Per-Viewer Agent & Goal-Directed Planning**: Persistent per-viewer agent owning state, evidence precedence rules (`app_settings` > `subtitle` > `profile`), versioned goal evaluation, plan reuse, purchase-triggered replanning, model call budgets (8 model / 20 tool calls), and machine-readable decision audit records.
- **Phase 3: Action Execution, Verification & Reliability**: Independent action verification (quiet hours 22:00-08:00, channel consent, 1 msg/day limit, 3-title homepage minimum), content prompt-injection defense, circuit breaker & monotonic latency timing, local mock action executor, and a 10-scenario surprise event test suite.
- **Phase 4: Replay, Outcome Judgment & Impact Measurement**: Reproducible replay runner engine with checkpoint resume (`ReplayCheckpoint`), dedicated outcome evaluator (`SUCCEEDED`, `FAILED`, `INCONCLUSIVE`, `PENDING`), randomized-holdout Intention-To-Treat (ITT) causal impact analysis, operational latency reporting, and 6 sample run artifacts.

---

## Environment Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Virtual environment support

### 2. Setup Virtual Environment & Dependencies
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
pip install -e .
```

### 3. Environment Variables
Copy the template configuration:
```bash
cp .env.example .env
```
Default parameters configured in `.env.example`:
- `DATABASE_URL`: `sqlite:///./ott_dialect.db`
- `FIXTURE_DIR`: `./data/fixtures`
- `CATALOGUE_PATH`: `./data/fixtures/catalogue.csv`
- `LOG_LEVEL`: `INFO`

---

## Commands Reference

### 1. Database Initialization & Ingestion
```powershell
# Initialize DB tables and SQLite partial unique index
$env:PYTHONPATH="src"; python -m ott_agent.cli.main init

# Ingest all fixtures
$env:PYTHONPATH="src"; python -m ott_agent.cli.main ingest --all

# Ingest the 1,500-title catalogue
$env:PYTHONPATH="src"; python -m ott_agent.cli.main ingest --catalogue data/fixtures/catalogue.csv

# View database status summary
$env:PYTHONPATH="src"; python -m ott_agent.cli.main status
```

### 2. Trigger Per-Viewer Agent Decision
```powershell
$env:PYTHONPATH="src"; python -m ott_agent.cli.main trigger VWR_BHO_009
```

### 3. Replay Runner & Artifact Generation
Run reproducible replay against trigger events to simulate decisions, actions, and outcomes:
```powershell
# Fresh replay (re-evaluating from start of trigger stream)
$env:PYTHONPATH="src"; python -m ott_agent.cli.main replay --input data/fixtures/events.jsonl --output sample_run --fresh --seed 42
```

#### Generated Sample Run Artifacts (`sample_run/`):
- `sample_run/decisions.jsonl` — Machine-readable decision audit records (provenance, confidence, rationale)
- `sample_run/actions.jsonl` — Executed and independently verified actions (`HOMEPAGE_ROW`, etc.)
- `sample_run/outcomes.jsonl` — Outcome classifications (`SUCCEEDED`, `FAILED`, `INCONCLUSIVE`)
- `sample_run/latency_report.json` — Operational latency distributions & call budget counters
- `sample_run/impact_report.md` — Randomized holdout Intention-To-Treat (ITT) causal impact evaluation
- `sample_run/final_report.md` — Executive replay report

### 4. Running Backend REST API & Frontend Interactive Docs
```powershell
python -m uvicorn ott_agent.main:app --host 127.0.0.1 --port 8000
```
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 5. Running Automated Tests
```powershell
pytest -v
```
All **43 automated unit, integration, and surprise event tests** pass cleanly.

> **Note on Pytest Warning**:
> Pytest emits a `StarletteDeprecationWarning` regarding upstream `TestClient` importing `httpx`. This is an upstream informational warning in Starlette/FastAPI's test utility and does not affect correctness or test execution.

---

## Content Catalogue Dataset & Provenance

The platform supports a comprehensive **1,500-title dataset** ([`data/fixtures/catalogue.csv`](data/fixtures/catalogue.csv) and [`data/content_catalogue.csv`](data/content_catalogue.csv)):
- **8 Supplied Titles** (`show_201` – `show_208`): Labeled with `data_origin: SUPPLIED`.
- **1,492 Scaled Synthetic Titles** (`synthetic_0001` – `synthetic_1492`): Labeled with `data_origin: SYNTHETIC_TEST_DATA`.
- **6 Arabic Dialects Covered**: Egyptian Arabic (`ar-EG`), Levantine Arabic (`ar-LB`, `ar-SY`), Gulf Arabic (`ar-AE`), Maghrebi Arabic (`ar-MA`), Iraqi Arabic (`ar-IQ`), and Sudanese Arabic (`ar-SD`).
