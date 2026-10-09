# KNOWN LIMITATIONS & ASSUMPTIONS: OTT Dialect Platform (Phase 1 & Phase 2)

## 1. Missing Original Datasets & Replay Runner

- **Workspace State**: The workspace was initially empty. As instructed, missing datasets and replay scripts were replaced by local mock fixtures in `data/fixtures/`.
- **Replay Script Testing**: We explicitly document that the original proprietary replay runner script was unavailable; local test suites validate ingestion, evidence precedence, planning, budget enforcement, and decision audit generation on sanitized mock fixtures.

---

## 2. Underspecified Goals & Unavailable Signals

- **Underspecified Goals**: Goals lacking explicit numeric threshold boundaries (e.g. `UNDERSPECIFIED_GENRE_BOOST`) are classified as `UNDERSPECIFIED` and evaluated under a conservative policy (abstain or default minimal intervention).
- **Unavailable Success Signals**: Goal rules requiring metrics absent from the event stream (e.g. `churn_risk_score`) are classified as `UNSUPPORTED_SIGNAL` and excluded from activation.

---

## 3. Machine-Readable Decision Output & JSONL Compatibility

- Decisions are saved in the `decisions` table with complete JSON audit fields and can be exported to standard `JSONL` format via `ott-cli export-decisions --output decisions.jsonl`.
