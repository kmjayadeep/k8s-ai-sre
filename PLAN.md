# k8s-ai-sre Plan

## Product Goal

Operate `k8s-ai-sre` as a reliable, service-first SRE assistant that completes this loop safely:

1. alert or manual request enters the API
2. investigation gathers real cluster evidence
3. agent proposes guarded remediation actions
4. operator is notified and explicitly approves or rejects
5. approved actions execute with guardrails and auditable state

## Current Baseline (April 7, 2026)

Implemented and validated:

- FastAPI investigation + Alertmanager webhook paths
- Telegram notification and command approval flow (`/incident`, `/status`, `/approve`, `/reject`)
- token-guarded HTTP operator action decisions (`POST /actions/{action_id}/approve|reject`) for non-interactive E2E validation
- fail-fast startup preflight for required runtime contract (`MODEL_NAME` + API key, Telegram token/chat pairing, `WRITE_ALLOWED_NAMESPACES` non-empty)
- guarded actions (`delete-pod`, `rollout-restart`, `scale`, `rollout-undo`)
- fail-closed mutation preflight with `kubectl auth can-i` checks and target readability checks before execution
- fail-closed write namespace contract: startup requires non-empty `WRITE_ALLOWED_NAMESPACES`
- action lifecycle safety checks (pending-only transitions, expiry handling, retry safety)
- action audit fields for approver identity/source, executed target details, and terminal execution result
- SQLite-backed incident/action persistence with atomic save (PR #43 + PR #54)
- read-only web incident inspector (`/` + `/incidents`) for operator inspection of past incidents
- incident API contract regression tests that freeze `IncidentResponse`/`IncidentsResponse` payload keys across `/investigate`, `/webhooks/alertmanager`, `/incidents`, and `/incidents/{incident_id}`
- error taxonomy: structured `{"code","message"}` HTTP errors and `[code] message` Telegram error prefixes
- CI test workflow for PRs and `main`
- in-cluster end-to-end validation of alert -> propose -> notify -> approve -> execute
- repeated kind reliability validation runner (`scripts/e2e_reliability_kind.sh`, N>=5 runs, evidence bundles)
- deterministic proposal fallback for `deployment` and `pod` investigations when the model answer omits proposal tool calls
- full kind runbook for real alert generation with PrometheusRule + Alertmanager webhook routing (`scripts/e2e_full_stack_kind.sh`)
- Prometheus-compatible operator loop-health metrics endpoint (`GET /metrics`) covering investigation latency, proposal totals, approval latency, and execution outcomes

Known limits:

- persistence is local-file only (not HA)
- approval identity is currently header/chat-derived and not federated with cluster identity providers
- restart recovery semantics during in-flight pending/approved actions now tested

## Prioritized Next Steps

### P0: Production Safety Gate ✅ COMPLETE

Exit criteria met:

- no unsafe execution path found in repeated reliability runs ✅
- all required startup config validated preflight (MODEL_NAME, API key, Telegram pairing, WRITE_ALLOWED_NAMESPACES) ✅
- canonical deploy + rollback runbook documented in `docs/deployment.md` ✅
- on-call can execute runbook without code changes ✅

### P1: Persistence and Recoverability

1. ~~Replace JSON files with SQLite default~~ ✅ DONE (PR #43)
2. ~~Atomic save() transaction safety~~ ✅ DONE (PR #54)
3. ~~Recovery semantics on restart during in-flight pending/approved actions~~ ✅ DONE (PR #61)
   - restart tests show no lost or duplicated terminal actions
   - SQLite-backed store does not change external behavior

### P1: Contract and Observability Stability

1. ~~Freeze response contracts~~ ✅ DONE (PR #49)
2. ~~Add operator-facing telemetry + error taxonomy~~ ✅ DONE (PR #50, PR #22)
3. ~~Observability dashboards and alerts~~ ✅ DONE (PR #63)
   - alert rules for approval loop health (investigation latency, approval SLA breach, execution failure rate)
   - Grafana dashboard for loop health monitoring
   - dashboards/alerts can answer: "is approval loop healthy right now?"

### P2: Scale Readiness

1. Multi-tenant safety boundaries
   - namespace and chat allow-list governance per environment
   - explicit tenancy model for incident/action IDs and access

2. Queueing and backpressure
   - protect Telegram/API loop from burst alerts
   - ensure investigation/execution remains bounded under load

Exit criteria:
- documented and tested behavior under burst and partial-outage scenarios

## Active PR / Workstream Focus

- keep PRs atomic and rebase-only
- prioritize merge order for safety-critical paths first
- avoid new feature sprawl until P1 gate is complete

## Plan Maintenance Rules

- update this file whenever production assumptions, priorities, or architecture truth changes
- keep this document concise and execution-oriented
- move detailed experiment logs to issue threads and daily memory notes
