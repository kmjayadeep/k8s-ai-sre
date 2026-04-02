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
- read-only web incident inspector (`/` + `/incidents`) for operator inspection of past incidents
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

### P0 Execution Queue (next implementation slices)

1. Startup preflight + fail-fast config validation
- add explicit startup checks for required secrets/env values, timeout bounds, and namespace guardrail config
- fail service boot with actionable errors when required config is missing or invalid
- add unit tests for invalid/missing config combinations

2. Approval actor audit trail and execution evidence
- persist approver identity (chat/user), approval timestamp, and execution result metadata in action records
- expose audit metadata in `/incidents` and `/incidents/{id}` responses and Telegram status views
- add contract tests to prevent accidental audit field regressions

3. Idempotent execution lock and restart safety
- prevent double execution of the same approved action during retries/restarts
- add explicit transition guardrails for `pending -> approved -> executing -> terminal`
- add tests for duplicate approve/retry paths and restart simulation

4. Canonical runbook completion
- finalize one deployment/runbook path for homelab and one rollback path
- include degraded-mode operations when Telegram is unavailable
- include evidence checklist for alert->approve->execute validation run

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

### P1 Execution Queue (after P0 gate)

1. Storage backend abstraction hardening
- keep existing `KeyValueStore` contract but isolate serialization and record versioning boundaries
- define migration-safe schemas for incident/action records

2. SQLite store implementation (default path)
- implement SQLite-backed incident/action store adapters
- set SQLite as default persistence backend for local and homelab runs
- keep JSON store as explicit fallback mode for debugging

3. Restart/recovery behavior contract
- define startup reconciliation behavior for in-flight actions (pending/approved/executing)
- add integration tests that kill/restart process mid-lifecycle and verify terminal correctness

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

## Active Issue Candidates

Create and run these as atomic PR-sized issues in order:

1. `AIE-next-1`: startup preflight validation + fail-fast errors
2. `AIE-next-2`: action audit metadata (approver + execution result) end-to-end
3. `AIE-next-3`: idempotent execution transitions + duplicate prevention tests
4. `AIE-next-4`: SQLite incident/action adapters with parity tests
5. `AIE-next-5`: restart reconciliation integration tests
6. `AIE-next-6`: metrics + health signals for approval loop latency/failure

## Active PR / Workstream Focus

- keep PRs atomic and rebase-only
- prioritize merge order for safety-critical paths first
- avoid new feature sprawl until P0 gate is complete

## Plan Maintenance Rules

- update this file whenever production assumptions, priorities, or architecture truth changes
- keep this document concise and execution-oriented
- move detailed experiment logs to issue threads and daily memory notes
