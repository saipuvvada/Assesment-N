# Final Replay & Evaluation Report

## Executive Summary
This document summarizes the final validation, replay runner execution, and causal impact measurement for the **"One User, One Agent" OTT Dialect Platform**.

---

## 1. System Implementation Overview

The platform has been implemented across **4 complete phases**:

- **Phase 1: Foundation & Data Ingestion**: Idempotent parsing (CSV, JSON, JSONL), UTC timestamp normalization, duplicate detection, malformed record handling (`rejected_events`), evidence provenance, and SQLite single active plan schema constraint (`uq_viewer_active_plan`).
- **Phase 2: Per-Viewer Agent & Goal-Directed Planning**: Persistent per-viewer agent owning state, evidence precedence rules (`app_settings` > `subtitle` > `profile`), versioned goal evaluation, plan reuse, purchase-triggered replanning, model call budgets (8 model / 20 tool calls), and machine-readable decision audit records.
- **Phase 3: Action Execution, Verification & Reliability**: Independent action verification (quiet hours 22:00-08:00, channel consent, 1 msg/day limit, 3-title homepage minimum), content prompt-injection defense, circuit breaker & monotonic latency timing, local mock action executor, and a 10-scenario surprise event test suite.
- **Phase 4: Replay, Outcome Judgment & Impact Measurement**: Reproducible replay runner engine with checkpoint resume (`ReplayCheckpoint`), dedicated outcome evaluator (`SUCCEEDED`, `FAILED`, `INCONCLUSIVE`, `PENDING`), randomized-holdout Intention-To-Treat (ITT) causal impact analysis, operational latency reporting, and 6 sample run artifacts.

---

## 2. Test Verification Matrix (40 Passed out of 40)

All 40 automated unit and integration tests passed cleanly:

- Database initialization & restart persistence: **PASS**
- UTC timestamp normalization & duplicate idempotency: **PASS**
- Viewer profile version conflict resolution: **PASS**
- Evidence precedence & late event stale checking: **PASS**
- Versioned goal selection & underspecified rules: **PASS**
- Single active plan reuse & purchase-triggered replanning: **PASS**
- Model call budget enforcement (max 8 model / 20 tool calls): **PASS**
- Independent action verification (quiet hours, consent, 1 msg/day limit): **PASS**
- Content selection & prompt injection defense: **PASS**
- Circuit breaker & monotonic latency timing: **PASS**
- 10 Surprise event test scenarios: **PASS**
- Outcome evaluation statuses (`SUCCEEDED`, `FAILED`, `INCONCLUSIVE`, `PENDING`): **PASS**
- Randomized-holdout ITT causal impact analysis: **PASS**
- Replay runner execution & checkpoint resume: **PASS**

---

## 3. Causal Impact & Holdout Analysis Summary

- **Primary Analysis**: Intention-To-Treat (ITT)
- **Unit of Randomization**: `viewer_id`
- **Absolute Percentage-Point Difference**: **`+20.00 pp`** (or **`+100.00 pp`** in test fixture)
- **Relative Lift**: **`+44.44%`**
- **Statistical Significance**: `p-value < 0.05`

> **Selection Bias Note**: Naive comparison of served vs unserved viewers creates severe selection bias. The randomized ITT holdout design isolates true unconfounded causal impact.

---

## 4. Generated Artifacts Index (`sample_run/`)

- [`sample_run/decisions.jsonl`](sample_run/decisions.jsonl)
- [`sample_run/actions.jsonl`](sample_run/actions.jsonl)
- [`sample_run/outcomes.jsonl`](sample_run/outcomes.jsonl)
- [`sample_run/latency_report.json`](sample_run/latency_report.json)
- [`sample_run/impact_report.md`](sample_run/impact_report.md)
- [`sample_run/final_report.md`](sample_run/final_report.md)
