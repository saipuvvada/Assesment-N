# ARCHITECTURE DOCUMENTATION: OTT Dialect Platform (Phase 1 & Phase 2)

## 1. System Overview & Agentic Workflow

The OTT Dialect Platform implements a per-viewer agentic framework where every viewer is managed by a persistent **Viewer Agent**. The agent owns viewer state, evidence-backed facts, goal selection, plan lifecycle management, and decision audit records.

```
                    +-----------------------------+
                    |  App-Open / Event Trigger   |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    |    Viewer Agent Service     |
                    +--------------+--------------+
                                   |
         +-------------------------+-------------------------+
         |                         |                         |
         v                         v                         v
 +---------------+         +---------------+         +---------------+
 |  Evidence &   |         | Goal Selection|         | Planner &     |
 |  Precedence   |         | Engine        |         | Replanning    |
 +---------------+         +---------------+         +---------------+
         |                         |                         |
         +-------------------------+-------------------------+
                                   |
                                   v
                    +-----------------------------+
                    |   Model Provider (Mock/LLM) |
                    | (Budget: 8 calls, 20 tools) |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | Machine-Readable Audit JSON |
                    +-----------------------------+
```

---

## 2. Key Phase 2 Architectural Concepts

### A. Evidence Provenance & Conflict Resolution Rules
Every fact stored in `viewer_facts` contains:
- `fact_key` & `fact_value`
- `source_type` (`app_settings`, `purchase_event`, `subtitle_change`, `watch_start`, `profile`)
- `observation_time` & `received_time`
- `confidence` & `has_conflict` flags
- `resolution_rule` & `resolution_reason`

#### Precedence & Freshness Rules
1. **Dialect Preference**: `app_settings` (100) > `subtitle_change` (80) > `watch_start` (60) > `profile` (40).
2. **Subscription & Entitlement**: Verified purchase events (`purchase_event`, precedence 100) override stale profile status (`profile`, precedence 30).
3. **Late Events**: Out-of-order late events are inserted into event history, but older observation times cannot overwrite newer facts (`LATE_EVENT_STALE_RULE`).
4. **Unresolved Conflicts**: Disagreements between sources of equal precedence are preserved with `has_conflict=True` for audit.

### B. Goal Selection & Rule Semantics
- **Versioned Goal Catalogue**: Versioned goals stored in `goals` table.
- **Underspecified Goals**: Goal rules lacking explicit threshold bounds (e.g. `UNDERSPECIFIED_GENRE_BOOST`) are flagged `UNDERSPECIFIED` and evaluated under a conservative policy.
- **Unavailable Success Signals**: Goal rules requiring unavailable signals (e.g. `churn_risk_score`) are marked `UNSUPPORTED_SIGNAL` and excluded from goal activation.
- **Priority Policy**: Highest version retention goal matching dialect and viewer state.

### C. Single Active Plan & Incremental Replanning
- **Database & Service Guard**: Enforces exactly one `ACTIVE` plan per viewer using a SQLite partial unique index (`uq_viewer_active_plan`).
- **Plan Reuse**: Reuses existing active plan on app-open triggers if goal conditions remain unchanged.
- **Purchase Replanning**: Verified purchase events automatically cancel free-tier plans (`plan_status = 'CANCELLED'`).

### D. Model Provider Abstraction & Call Budgets
- **Provider Interface**: Abstract class `BaseModelProvider` supporting `RuleBasedModelProvider` and `HostedModelProvider`.
- **Budget Limits**: Enforces max **8 model calls** and **20 tool calls** per decision with configurable timeouts.
- **Fallback**: Automatic fallback to deterministic mock mode on API timeout, rate limit, or model call limit.

---

## 3. Machine-Readable Decision Audit API

Endpoints added in Phase 2:

| Endpoint | Method | Response | Description |
|---|---|---|---|
| `/agent/trigger` | POST | Machine-readable Audit JSON | Process app-open trigger for a viewer |
| `/viewers/{viewer_id}/goal-plan` | GET | `GoalPlanResponse` | Read current goal and active plan |
| `/viewers/{viewer_id}/evidence` | GET | `EvidenceResponse` | View evidence provenance & conflicts |
| `/decisions/{decision_id}/audit` | GET | Machine-readable Audit JSON | Full decision audit record |
