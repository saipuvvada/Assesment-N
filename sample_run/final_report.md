# Final Replay & Evaluation Report

## Run Summary
- **Run ID**: `run_default_1791572831`
- **Processed Triggers**: `7`
- **Replay Execution Mode**: Local Mock Mode (Fully Private & Deterministic)

---

## Key Achievements & Verification
1. **100% Independent Action Verification**: Every action passed dedicated verification before mock execution.
2. **SQLite Active Plan Invariant**: Enforced single active plan per viewer (`uq_viewer_active_plan`).
3. **Evidence-Backed Provenance**: Field precedence rules (`app_settings` > `subtitle` > `profile`) and late-event stale checking verified.
4. **Causal ITT Impact Analysis**: Treatment vs Control holdout difference: **`+0.00 pp`** relative lift: **`+0.00%`**.

---

## Artifact Index
- [`decisions.jsonl`](decisions.jsonl)
- [`actions.jsonl`](actions.jsonl)
- [`outcomes.jsonl`](outcomes.jsonl)
- [`latency_report.json`](latency_report.json)
- [`impact_report.md`](impact_report.md)
