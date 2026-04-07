# Plan Snapshot

This page summarizes the active direction from `PLAN.md`.

## Product Goal

Operate `k8s-ai-sre` as a reliable, service-first SRE assistant that safely closes this loop:

1. request or alert enters API
2. investigation gathers real evidence
3. agent proposes guarded remediation actions
4. operator explicitly approves or rejects
5. approved actions execute with guardrails and auditable state

## Current baseline

Implemented and validated:

- API investigation and Alertmanager webhook paths
- Telegram notification and approval command flow (`/incident`, `/status`, `/approve`, `/reject`)
- token-guarded HTTP operator action decisions (`POST /actions/{action_id}/approve|reject`)
- fail-fast startup preflight for required runtime config
- guarded actions (`delete-pod`, `rollout-restart`, `scale`, `rollout-undo`)
- fail-closed RBAC preflight (`kubectl auth can-i`) and target readability checks for mutating actions
- fail-closed write namespace contract: startup requires non-empty `WRITE_ALLOWED_NAMESPACES`
- action lifecycle safety checks and audit fields for operator identity and execution result
- SQLite-backed incident/action persistence (default: `/tmp/k8s-ai-sre-store.sqlite3`)
- read-only web incident inspector for operator inspection of past incidents
- CI test workflow and in-cluster end-to-end validation path
- full in-cluster alert pipeline exercise (Prometheus + Alertmanager)
- repeated reliability evidence runner (`scripts/e2e_reliability_kind.sh`, N>=5)
- Prometheus-compatible loop-health metrics endpoint (`GET /metrics`)
- incident API contract regression tests freezing response payload keys
- deterministic proposal fallback for `deployment` and `pod` targets

**P0 Production Safety Gate: COMPLETE** — all PRs merged, reliability validation passed.

## Priority direction

Current active work is P1: Persistence and Recoverability (SQLite done, atomic save PR merged) and observability.

Read `PLAN.md` for detailed exit criteria and sequence.
