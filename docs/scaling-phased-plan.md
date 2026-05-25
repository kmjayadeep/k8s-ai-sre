# Phased Scaling Plan

This plan evolves `k8s-ai-sre` from the current service-first MVP into a scalable control plane without jumping directly to a distributed architecture. The first goal is a modular monolith: split core responsibilities inside the same container while keeping runtime behavior unchanged.

See also: [incremental architecture diagram](scaling-target-architecture.html).

## Guiding principles

- Keep safety boundaries intact: the model proposes, humans approve, execution re-checks guardrails.
- Prefer small, reviewable PRs over broad rewrites.
- Do not introduce external infrastructure until internal service boundaries are clear.
- Preserve current deployment behavior during early phases.
- Keep incident/action state auditable at every step.

## Phase 1: Modular monolith, same container

**Goal:** separate core components in code while keeping one FastAPI process, one container, SQLite, Telegram polling, and synchronous investigation behavior.

### Scope

- Extract incident lifecycle orchestration from HTTP routes.
- Keep `/investigate` and `/webhooks/alertmanager` response behavior unchanged.
- Keep existing store abstraction and SQLite backend.
- Keep existing action execution path and approval semantics.
- Add service-level tests around extracted boundaries.

### Target internal components

| Component | Responsibility | Initial module target |
|---|---|---|
| API + Ingestion | FastAPI routes, auth, request validation, target normalization | `app/http.py`, later `app/ingestion.py` |
| Incident Service | dedup, create/update incidents, lifecycle events, action attachment | `app/incidents/service.py` |
| Investigation Service | evidence orchestration, model call, deterministic fallback proposals | `app/investigate.py`, later `app/investigation/service.py` |
| Notification Service | Telegram notification boundary, future Slack boundary | `app/notifier.py`, later `app/notifications/service.py` |
| Approval Service | approve/reject, actor identity, expiry handling | `app/actions.py`, later `app/approvals/service.py` |
| Action Executor | namespace allow-list, RBAC `can-i`, Kubernetes mutation helpers | `app/tools/actions.py`, later `app/executor/service.py` |

### Suggested PR order

1. Add `app/incidents/service.py` and move manual investigation orchestration behind service functions.
2. Move Alertmanager target ingestion/dedup orchestration into the incident service.
3. Extract Alertmanager target resolution helpers into a small ingestion module.
4. Wrap notification sending behind a notification service function.
5. Separate approval decision code from execution code at the service boundary.
6. Add service tests for deduplication, resolved alerts, notification status updates, and action attachment.

### Explicit non-goals

- No Kafka, NATS, SQS, or external queue.
- No separate worker Deployment.
- No Postgres migration.
- No multi-cluster agent.
- No broad Kubernetes Python client rewrite.

### Exit criteria

- `app/http.py` mainly handles HTTP concerns and delegates business orchestration.
- Incident, notification, approval, and execution boundaries are clear in code.
- Existing API contracts and tests continue to pass.
- A future in-process queue can be introduced without rewriting HTTP routes again.

## Phase 2: In-process async worker

**Goal:** remove long-running investigation work from the HTTP request path without adding external infrastructure.

### Scope

- Add an in-process investigation job queue.
- Return `202 Accepted` for new investigation requests where appropriate.
- Persist incident/event state before job execution starts.
- Add job status visibility through existing incident endpoints or a small queue-status endpoint extension.
- Keep SQLite/store abstraction as source of truth.

### Work items

- Define an `InvestigationJob` model with incident ID, target, source, and idempotency key.
- Add bounded in-process queue and worker loop.
- Reuse existing backpressure limits.
- Store terminal investigation state: completed, failed, skipped, deduplicated.
- Add retry policy for transient investigation failures.

### Exit criteria

- HTTP ingestion returns quickly for investigation-producing requests.
- Duplicate target requests reuse or append to existing active incidents.
- Worker crashes/failures are visible in incident history.
- No action can execute without the same approval and guardrail checks as today.

## Phase 3: Production-safe persistence and audit

**Goal:** harden state management before distributing components.

### Scope

- Move the default production store path away from `/tmp`, typically to a PVC.
- Add `cluster_id` to incident and action records.
- Strengthen idempotency keys for alert ingestion and manual requests.
- Add immutable audit events for proposal, approval, rejection, execution, and failure.
- Add action expiry and fresh validation before execution if not already present for all action paths.

### Work items

- Document production store configuration.
- Add migration/backfill approach for new record fields.
- Add structured audit event helpers.
- Expand metrics around queue latency, investigation duration, approval latency, and action outcomes.

### Exit criteria

- Production deployments do not rely on ephemeral `/tmp` state.
- Every action has a traceable proposal, approval/rejection, and execution result.
- Incident records identify the cluster they belong to.
- Failed operations reach a terminal, inspectable state.

## Phase 4: Split runtime components inside the same image

**Goal:** keep one container image but allow different process roles when needed.

### Scope

- Add runtime role selection, for example `K8S_AI_SRE_COMPONENTS=api,worker,telegram,executor`.
- Use the same image for API-only, worker-only, notifier-only, or executor-only processes.
- Keep the default role set compatible with the current all-in-one deployment.

### Work items

- Add `app/runtime.py` for component startup.
- Move Telegram polling startup out of HTTP server startup.
- Add process-role health reporting.
- Add Helm values for optional role-specific Deployments, disabled by default.

### Exit criteria

- Current deployment still works as all-in-one by default.
- Operators can run separate API and worker processes using the same image.
- Component startup is explicit and observable.

## Phase 5: Durable queue and Postgres

**Goal:** introduce external durability and horizontal worker scale after boundaries are stable.

### Scope

- Replace the in-process queue with a durable queue such as NATS JetStream, SQS/PubSub, or Kafka.
- Move production incident/action/audit storage to Postgres.
- Keep store and queue interfaces narrow so tests can still use in-memory or SQLite backends.

### Work items

- Define queue topics/events:
  - `incident.investigation.requested`
  - `incident.investigation.completed`
  - `action.proposed`
  - `action.approved`
  - `action.rejected`
  - `action.execution.requested`
  - `action.executed`
  - `notification.requested`
- Add dead-letter handling and replay documentation.
- Add worker autoscaling based on queue depth/lag.
- Add idempotent consumers.

### Exit criteria

- Investigation and execution workers can scale independently.
- Queue retries do not create duplicate active incidents or duplicate mutations.
- Postgres is the production source of truth.

## Phase 6: Policy, LLM gateway, and multi-cluster agents

**Goal:** evolve into a full control-plane architecture when scale and tenancy require it.

### Scope

- Add a policy engine for action schema validation, risk scoring, namespace policy, and approval thresholds.
- Add an internal LLM gateway for redaction, token budgeting, retries, fallback, and cost tracking.
- Add per-cluster agents that connect outbound to the central control plane over mTLS.

### Work items

- Define structured LLM output schema.
- Add secret/config redaction before model calls.
- Add server-side dry-run where supported before Kubernetes mutations.
- Add per-cluster and per-namespace concurrency controls.
- Add tenant/team isolation for multi-cluster operation.

### Exit criteria

- Central control plane does not need broad kubeconfigs for every cluster.
- Per-cluster agents use tightly scoped RBAC.
- LLM calls are governed, observable, and cost-tracked.
- High-risk actions require stronger approval policy.

## Summary roadmap

```text
Phase 1  Modular monolith, same container
Phase 2  In-process async worker
Phase 3  Production-safe persistence and audit
Phase 4  Split runtime roles using same image
Phase 5  Durable queue and Postgres
Phase 6  Policy, LLM gateway, multi-cluster agents
```

The immediate next step is Phase 1. It reduces coupling and prepares the project for scale without changing the operational model too early.
