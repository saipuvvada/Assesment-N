# TECHNICAL DISCUSSION GUIDE: OTT Dialect Platform

This document provides concise, implementation-specific answers to the core architectural and technical interview questions, based on the working design implemented in Phases 1–4.

---

## 1. How do you determine whether viewer evidence is current?

In our implementation ([`EvidenceService`](file:///c:/Users/Lenovo/Documents/ASSESMENT-N/src/ott_agent/services/evidence_service.py)), currency and truth are determined by combining **observation timestamps** with **field-specific source precedence** and **late-event freshness rules**:

1. **Source Precedence**: Different data sources carry different trust weights:
   - `dialect_preference`: `app_settings` (100) > `subtitle_change` (80) > `watch_start` (60) > `profile` (40).
   - `subscription_status`: Verified purchase events (`purchase_event`, 100) > Stale viewer profile (`profile`, 30).
2. **Late-Event Freshness Guard (`LATE_EVENT_STALE_RULE`)**:
   Incoming events arriving out-of-order (e.g. buffered offline events from days ago) are inserted into event history for provenance, but older observation times (`observation_time < latest_obs`) cannot overwrite newer facts.
3. **Audit Provenance**: Every decision audit record explicitly calculates and logs evidence age as `trigger_age_seconds` and `evidence_freshness_json`.

---

## 2. When should the agent do nothing?

The agent explicitly abstains (`status = "ABSTAINED"`, `proposed_action = "ABSTAIN"`) in the following deterministic conditions:

1. **No Eligible Goal**: When no goal in the catalogue matches the viewer's current state (e.g. engagement score below threshold).
2. **Unavailable Success Signals**: When a goal rule requires a metric absent from the stream (e.g. `churn_risk_score`).
3. **Underspecified Rules**: When a goal rule lacks explicit numeric thresholds (e.g. `UNDERSPECIFIED_GENRE_BOOST`), evaluated under a conservative policy.
4. **Independent Verification Failures**: When an intervention fails verification checks:
   - Quiet hours violation (22:00 to 08:00 in viewer's local time).
   - Channel consent denied (`MessageConsent` = False).
   - Daily frequency cap exceeded (max 1 message per viewer per local calendar day).
   - Homepage row failing to assemble at least **3 eligible titles**.
5. **Provider Failure / Call Budget Exceeded**: When model or tool call budgets (max 8 model, 20 tool calls) are exceeded and deterministic fallback dictates abstention.

---

## 3. How do you demonstrate causal impact?

Causal impact is demonstrated in [`RandomizedHoldoutAnalyzer`](file:///c:/Users/Lenovo/Documents/ASSESMENT-N/src/ott_agent/services/impact_analysis.py) using a **Randomized-Holdout Intention-To-Treat (ITT)** experimental design:

1. **Randomized Assignment**: Viewers are randomly assigned at the viewer level (`viewer_id`) to `treatment` or `control` (holdout).
2. **ITT Primary Comparison**: Compares the conversion rate of all assigned treatment viewers ($p_{\text{treatment}}$) against all assigned control viewers ($p_{\text{control}}$).
3. **Metrics Reported**:
   - Absolute percentage-point difference: $\Delta = p_{\text{treatment}} - p_{\text{control}}$ (e.g. $+20.00\text{ pp}$).
   - Relative Lift: $\text{Lift} = \frac{p_{\text{treatment}} - p_{\text{control}}}{p_{\text{control}}} \times 100\%$ (e.g. $+44.44\%$).
   - 95% Confidence Interval & two-tailed Z-test p-value.
4. **Addressing Naive Selection Bias**:
   Comparing only *served* viewers against unserved viewers introduces severe selection bias, because agents selectively target active, highly-engaged viewers. The randomized ITT holdout design isolates the unconfounded causal effect.

---

## 4. How would you handle 1,000 simultaneous app opens?

### Current Implemented Architecture:
- Thread-safe in-memory/file SQLite with `StaticPool`.
- SQLite partial unique index (`uq_viewer_active_plan`) for database-level concurrency protection.
- Monotonic clock timing (`time.monotonic()`) and `CircuitBreaker` pattern to prevent cascade failures.

### Production Scaling Proposal (Future Work):
1. **Database Migration**: Migrate from SQLite to PostgreSQL with row-level locks (`SELECT ... FOR UPDATE`) or distributed database (CockroachDB).
2. **Asynchronous Queue**: Ingest app-open triggers into an event streaming queue (Apache Kafka or AWS SQS) and process asynchronously via worker pools (Celery / Rust / Go workers).
3. **Durable State Caching**: Cache viewer state snapshots and rate limit counters in Redis Cluster (<2ms read latency).
4. **Horizontal Scaling**: Deploy stateless FastAPI application containers on Kubernetes (EKS) behind an Application Load Balancer (ALB).

---

## 5. Which decisions should never be automated without additional approval?

The following high-risk actions must **never** be fully automated without explicit human-in-the-loop authorization:

1. **Financial & Subscription Mutations**: Charging credit cards, altering subscription pricing, or granting free paid tier access.
2. **Account Status Operations**: Suspending, banning, or deleting user accounts.
3. **Unsanitized Content Execution**: Executing actions or messages containing untrusted text from catalogue descriptions or user inputs without prompt-injection sanitization.
4. **Broad Broadcast Messaging**: Dispatching mass push or WhatsApp broadcasts overriding quiet hours or channel consent boundaries.

---

## 6. How would you scale to 10 million viewers and 40 dialects?

### Production Scale Proposal (Future Work):

1. **Database Sharding**: Partition viewer records and event history by `hash(viewer_id)` across a distributed PostgreSQL or Cassandra cluster.
2. **Dialect Indexing & Vector Search**: Store catalogue items in Elasticsearch or Qdrant vector database indexed by `(dialect, language_variant, availability_window)` for sub-5ms content row assembly across 40 dialects.
3. **Edge Pre-computation**: Pre-compute viewer dialect preferences and quiet hour windows at edge nodes (Cloudflare Workers / AWS CloudFront) to serve instant homepage rows.
4. **Stream Processing**: Use Apache Flink / Kafka Streams to incrementally update viewer engagement features and facts in real time.

---

## 7. What did AI-generated code get wrong, and how did you verify it?

During development, empirical runtime verification caught several edge-case errors in AI-suggested code snippets:

1. **Missing Relationship Attributes**:
   - *Issue*: Initial SQLAlchemy model definitions omitted the `viewer` relationship attribute on `Decision` and `Action`, causing runtime `AttributeError` when generating decision audit payloads.
   - *Verification & Fix*: Caught via `pytest` API integration test failures; added explicit bidirectional relationships (`relationship("Viewer")`).
2. **Timezone Naive vs. Aware Datetime Arithmetic**:
   - *Issue*: Subtracting naive datetimes retrieved from SQLite from UTC-aware datetimes produced Python `TypeError: can't subtract offset-naive and offset-aware datetimes`.
   - *Verification & Fix*: Identified via pytest traceback in `test_late_event_freshness_rule`; created `ensure_utc()` helper to guarantee timezone awareness across all datetime operations.
3. **Idempotency Key Duplication Errors**:
   - *Issue*: Re-triggering the same event caused `sqlite3.IntegrityError: UNIQUE constraint failed: actions.idempotency_key` because code attempted to re-insert duplicate `Action` rows.
   - *Verification & Fix*: Caught during surprise event test execution (`test_surprise_10`); updated `agent_service.py` to query existing `Action` records by `idempotency_key` before insertion.
