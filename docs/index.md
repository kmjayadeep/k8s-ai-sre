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

## Start Here By Goal

### Operator path

- run the product locally: [Quick Start](quickstart.md)
- deploy into a cluster: [Deployment Guide](deployment.md)
- understand the system design: [Architecture Guide](architecture.md)

### Contributor path

- start the repo workflow: [Contributing](contributing.md)
- local setup and request examples: [Developer Guide](developer.md)
- choose a validation lane: [Validation guide](testing.md)
- run exact commands: [repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md)

## Source Of Truth

This docs site must stay aligned with repository sources:

- product behavior: `README.md`
- validation runbook: `TESTING.md`
- deploy/rollback and startup contract: `docs/deployment.md`
- near-term priorities and constraints: `PLAN.md`

When these sources change, update matching docs pages in the same pull request.

## Contributor Navigation

Use [Contributing](contributing.md) as the entry page for repository workflow. It links setup, validation, PR handoff, QA evidence, and merge ownership in order.
