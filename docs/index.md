# k8s-ai-sre Documentation

`k8s-ai-sre` is an AI-assisted Kubernetes incident investigator with guarded remediation.

## Current Product Scope

The repository currently implements:

- investigation for pods and deployments with real Kubernetes reads
- evidence collection from resource state, events, logs, and optional Prometheus queries
- API-triggered investigations (`/investigate`) and Alertmanager webhook handling (`/webhooks/alertmanager`)
- SQLite-backed persistence for incidents and pending actions (default path `/tmp/k8s-ai-sre-store.sqlite3`)
- Telegram notifications and approval commands (`/incident`, `/status`, `/approve`, `/reject`)
- guarded remediation actions that require explicit approval before execution

## Operator Loop

1. an alert or manual request targets a Kubernetes object
2. the agent gathers evidence and explains likely cause
3. the agent proposes remediation actions
4. an operator approves or rejects the proposal
5. approved actions execute through guardrails

## Source Of Truth

This docs site must stay aligned with repository sources:

- product behavior: `README.md`
- validation runbook: `TESTING.md`
- deploy/rollback and startup contract: `docs/deployment.md`
- near-term priorities and constraints: `PLAN.md`

When these sources change, update matching docs pages in the same pull request.

## Contributor Navigation

Use these pages for repository workflow:

- `quickstart.md` for first-time local setup
- `developer.md` for contributor validation commands and PR handoff
- `testing.md` and `TESTING.md` for validation depth and end-to-end runbooks
- `maintainers.md` for docs ownership and merge routing
