# k8s-ai-sre Plan

## Product Goal

Operate `k8s-ai-sre` as a reliable, service-first SRE assistant that completes this loop safely:

1. alert or manual request enters the API
2. investigation gathers real cluster evidence
3. agent proposes guarded remediation actions
4. operator is notified and explicitly approves or rejects
5. approved actions execute with namespace/RBAC guardrails and auditable state

## Current Baseline (April 2, 2026)

Implemented and validated:

- FastAPI investigation + Alertmanager webhook paths
- Telegram notification and command approval flow (`/incident`, `/status`, `/approve`, `/reject`)
- guarded actions (`delete-pod`, `rollout-restart`, `scale`, `rollout-undo`)
- action lifecycle safety checks (pending-only transitions, expiry handling, retry safety)
- local JSON-backed incident/action persistence with store abstraction
- CI test workflow for PRs and `main`
- in-cluster end-to-end validation of alert -> propose -> notify -> approve -> execute

Known limits:

- persistence is local-file only (not HA)
- approval and execution are not yet backed by Kubernetes-native identity/audit surfaces
- rollout readiness still depends on manual environment/secret setup

## Product Direction Update

- near-term product focus is homelab-first quick start
- default persistence target should be SQLite (simple single-binary setup)
- PostgreSQL is deferred as future extension work, not part of current plan

## Prioritized Next Steps

### P0: Production Safety Gate (must complete before broader rollout)

1. Harden execution authorization
- align action execution with Kubernetes RBAC service account boundaries
- fail closed on any target-resolution or permission ambiguity
- add explicit audit log fields for who approved, what executed, and result

2. Operational runbook completeness
- finalize one canonical deploy + rollback runbook
- define required env/secret contract with validation at startup
- document incident response steps for Telegram/API degradation

3. Reliability checks in cluster
- run repeated live validation in kind or dev cluster (N>=5 runs)
- verify no duplicate or unsafe execution under retries/restarts
- capture evidence bundle (logs, incident IDs, action IDs, cluster state diffs)

Exit criteria:
- no unsafe execution path found in repeated runs
- all required startup config validated preflight
- on-call can execute runbook without code changes

### P1: Persistence and Recoverability

1. Replace JSON files with SQLite default
- keep zero-friction local startup for homelab users
- migrate incident/action stores to a SQLite-backed implementation
- preserve current API/Telegram contract shape and action lifecycle semantics

2. Recovery semantics
- define behavior on restart during pending/approved actions
- ensure idempotent approval/execution after process restart

Exit criteria:
- restart tests show no lost or duplicated terminal actions
- SQLite-backed store does not change external behavior

### P1: Contract and Observability Stability

1. Freeze response contracts
- keep normalized incident payloads across create/read endpoints
- version or document any breaking schema changes

2. Add operator-facing telemetry
- metrics for investigation latency, proposal rate, approval latency, execution success/failure
- clear error taxonomy in HTTP and Telegram responses

Exit criteria:
- dashboards/alerts can answer: "is approval loop healthy right now?"
- contract tests prevent unintentional payload drift

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
- avoid new feature sprawl until P0 gate is complete

## Plan Maintenance Rules

- update this file whenever production assumptions, priorities, or architecture truth changes
- keep this document concise and execution-oriented
- move detailed experiment logs to issue threads and daily memory notes
