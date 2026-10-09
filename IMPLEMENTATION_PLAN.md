# IMPLEMENTATION PLAN: OTT Dialect Platform (Phase 1, Phase 2, Phase 3 & Phase 4)

## 1. System Overview & Context
This project implements the complete 4-phase "One User, One Agent" OTT Dialect Platform. Phase 4 completes the agentic loop with automated replay runner execution, checkpointed resumption, evidence-backed outcome evaluation (`SUCCEEDED`, `FAILED`, `INCONCLUSIVE`, `PENDING`), randomized-holdout Intention-To-Treat (ITT) causal impact analysis, latency metrics reporting, and sample run artifact generation.

---

## 2. Phase 4 Component Mapping

| Component Category | Description / Features | Implementation File(s) | Test File(s) |
|---|---|---|---|
| **Outcome Evaluator & Closing Loop** | Goal deadline calculation, success event matching (`SUCCEEDED`, `FAILED`, `INCONCLUSIVE`, `PENDING`), closing completed goals | `src/ott_agent/services/outcome_evaluator.py`<br>`src/ott_agent/services/outcome_simulator.py` | `src/ott_agent/tests/test_outcome_evaluator.py` |
| **Randomized-Holdout Impact Analysis** | ITT analysis, treatment vs control outcome rates, absolute diff, relative lift, 95% CI, p-value, bias explanation | `src/ott_agent/services/impact_analysis.py` | `src/ott_agent/tests/test_impact_analysis.py` |
| **Latency & Operational Metrics** | Monotonic wall-clock latency, Median, P95, Max latency, call budget distributions, rejection breakdowns | `src/ott_agent/services/latency_reporter.py` | `src/ott_agent/tests/test_latency_reporter.py` |
| **Replay Runner Engine** | Replay trigger processing, event time preservation, `ReplayCheckpoint` resume, 6 sample run artifact generation | `src/ott_agent/services/replay_runner.py`<br>`src/ott_agent/cli/replay.py` | `src/ott_agent/tests/test_phase4_replay_and_impact.py` |

---

## 3. Sample Run Artifact Outputs (`sample_run/`)
- `sample_run/decisions.jsonl` — Machine-readable decision audit trail
- `sample_run/actions.jsonl` — Executed/rejected actions and verification results
- `sample_run/outcomes.jsonl` — Evaluated outcomes (`SUCCEEDED`, `FAILED`, `INCONCLUSIVE`, `PENDING`)
- `sample_run/latency_report.json` — Detailed operational latency & budget distribution report
- `sample_run/impact_report.md` — Randomized holdout ITT causal impact analysis report
- `sample_run/final_report.md` — Executive summary of replay results and takeaways

---

## 4. Phase 4 Verification Checklist
- Replay command `ott-cli replay --input <file> --output sample_run` executes deterministically.
- Interrupted replays resume safely using `ReplayCheckpoint` without duplicate actions.
- Outcome statuses (`SUCCEEDED`, `FAILED`, `INCONCLUSIVE`, `PENDING`) respect deadlines and success signals.
- Missing success signals are marked `INCONCLUSIVE` rather than false failures.
- ITT impact analysis reports sample sizes, percentage point difference, lift, and 95% confidence intervals.
- All 36+ automated tests pass cleanly.
