# k8s-ai-sre Plan

## Product Goal

Operate `k8s-ai-sre` as a reliable, service-first SRE assistant that completes this loop safely:

1. alert or manual request enters the API
2. investigation gathers real cluster evidence
3. agent proposes guarded remediation actions
4. operator is notified and explicitly approves or rejects
5. approved actions execute with namespace/RBAC guardrails and auditable state

## Current Baseline (April 7, 2026)

Implemented and validated:

- FastAPI investigation + Alertmanager webhook paths
- Telegram notification and command approval flow (`/incident`, `/status`, `/approve`, `/reject`)
- token-guarded HTTP operator action decisions (`POST /actions/{action_id}/approve|reject`) for non-interactive E2E validation
- fail-fast startup preflight for required runtime contract (`MODEL_NAME` + API key, Telegram token/chat pairing rules, `WRITE_ALLOWED_NAMESPACES`)
- guarded actions (`delete-pod`, `rollout-restart`, `scale`, `rollout-undo`)
- fail-closed mutation preflight with `kubectl auth can-i` checks and target readability checks before execution
- fail-closed write namespace contract: startup requires non-empty `WRITE_ALLOWED_NAMESPACES`
- action lifecycle safety checks (pending-only transitions, expiry handling, retry safety)
- action audit fields for approver identity/source, executed target details, and terminal execution result
- SQLite-backed incident/action persistence with store abstraction (default path `/tmp/k8s-ai-sre-store.sqlite3`); atomic save via `BEGIN IMMEDIATE` transaction
- read-only web incident inspector (`/` + `/incidents`) for operator inspection of past incidents
- incident API contract regression tests that freeze `IncidentResponse`/`IncidentsResponse` payload keys across `/investigate`, `/webhooks/alertmanager`, `/incidents`, and `/incidents/{incident_id}`
- CI test workflow for PRs and `main`
- in-cluster end-to-end validation of alert -> propose -> notify -> approve -> execute
- deterministic proposal fallback for `deployment` and `pod` investigations when the model answer omits proposal tool calls
- full kind runbook for real alert generation with PrometheusRule + Alertmanager webhook routing (`scripts/e2e_full_stack_kind.sh`)
- repeated reliability evidence runner (`scripts/e2e_reliability_kind.sh`, N>=5)
- Prometheus-compatible operator loop-health metrics endpoint (`GET /metrics`) covering investigation latency, proposal totals, approval latency, and execution outcomes
- error taxonomy contracts: HTTP and Telegram error responses use structured `{ "code": "...", "message": "..." }` shape

Known limits:

- persistence is local-file only (not HA)
- approval identity is currently header/chat-derived and not federated with cluster identity providers
- rollout readiness still depends on manual environment/secret setup

## Product Direction

- homelab-first quick start is the near-term product focus
- SQLite is the default persistence target (PostgreSQL deferred as future extension)
- no new feature sprawl until P1 work is complete

## Prioritized Next Steps

### P0: Production Safety Gate — COMPLETE ✅

All PRs merged:

- PR #52: Fail-closed write namespace allow-list (startup rejects unset)
- PR #50: HTTP/Telegram error taxonomy contracts
- PR #51: Fail-fast startup config preflight
- PR #53: Fix missing X-Operator-Id header on approve curl calls
- PR #44: Repeated kind reliability evidence runner (N>=5)
- PR #43 (AIE-25): SQLite default persistence and restart semantics
- PR #54: Atomic save (BEGIN IMMEDIATE transaction)

### P1: Persistence and Recoverability

Remaining work:

1. Recovery semantics on restart (in-flight pending/approved actions)
   - define behavior on restart during pending/approved actions
   - ensure idempotent approval/execution after process restart

2. Observability dashboards and alerts
   - metrics for investigation latency, proposal rate, approval latency, execution success/failure
   - dashboards/alerts that answer "is approval loop healthy right now?"

Exit criteria:
- restart tests show no lost or duplicated terminal actions
- observability stack can answer loop health questions without code changes

### P1: Contract Stability

Remaining work:

1. Freeze response contracts
   - keep normalized incident payloads across create/read endpoints
   - regression assertions already in place; maintain on new additions

2. Clear error taxonomy
   - HTTP and Telegram responses already use `{ "code": "...", "message": "..." }` shape

Exit criteria:
- contract tests prevent unintentional payload drift
- all error codes documented

### P2: Scale Readiness

1. Multi-tenant safety boundaries
   - namespace and chat allow-list governance per environment
   - explicit tenancy model for incident/action IDs and access

2. Queueing and backpressure
   - protect Telegram/API loop from burst alerts
   - ensure investigation/execution remains bounded under load

Exit criteria:
- documented and tested behavior under burst and partial-outage scenarios

## Active Workstream Rules

- keep PRs atomic and rebase-only
- prioritize merge order for safety-critical paths first
- no new feature sprawl until P1 is complete

## Plan Maintenance Rules

- update this file whenever production assumptions, priorities, or architecture truth changes
- keep this document concise and execution-oriented
- move detailed experiment logs to issue threads and daily memory notes
