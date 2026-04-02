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

Implemented baseline includes:

- API investigation and Alertmanager webhook paths
- Telegram notification and approval command flow
- guarded actions (`delete-pod`, `rollout-restart`, `scale`, `rollout-undo`)
- fail-closed RBAC preflight (`kubectl auth can-i`) and target readability checks for mutating actions
- action audit fields for operator identity/source and execution result details
- local JSON persistence for incidents/actions
- CI tests and in-cluster end-to-end validation path
- full in-cluster monitoring validation path using Prometheus + Alertmanager rule/webhook wiring

## Priority direction

Current priority in `PLAN.md` is the production safety gate before broader rollout:

- harden execution authorization and auditability
- complete runbook and startup config validation
- repeatedly validate reliability in-cluster

Read `PLAN.md` for detailed exit criteria and sequence.
