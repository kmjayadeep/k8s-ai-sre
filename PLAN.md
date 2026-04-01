# k8s-ai-sre Plan

## Goal

Operate `k8s-ai-sre` as a service-first Kubernetes incident investigator with guarded remediation:

1. an alert or manual API request targets a resource
2. the agent investigates with real cluster evidence
3. the agent creates pending remediation proposals when justified
4. Telegram is used to review and approve or reject those proposals
5. approved actions execute through namespace and approval guardrails

## Current State

### Implemented

- FastAPI is the primary interface.
- Telegram runs as a complementary operator interface.
- `main.py` starts the HTTP service directly.
- the service starts a real Telegram polling loop when Telegram is configured
- investigations use real `kubectl` reads
- evidence includes resource state, events, logs, workload pod lookup, and optional Prometheus queries
- the agent can call proposal tools for `delete-pod`, `rollout-restart`, `scale`, and `rollout-undo`
- proposed actions are stored with `action_ids` and `proposed_actions`
- incidents are persisted in a local JSON store
- actions are persisted in a local JSON store with expiry handling
- Telegram notifications include proposed action IDs and approval commands
- Telegram supports `/incident`, `/status`, `/approve`, and `/reject`
- approved actions execute through guarded action helpers
- action lifecycle transitions are now guarded so non-pending actions cannot be rejected and expired approvals/rejections fail closed
- write namespaces are constrained with `WRITE_ALLOWED_NAMESPACES`
- allowed Telegram chats are constrained with `TELEGRAM_ALLOWED_CHAT_IDS`
- structured logging is in place
- the container image, GHCR publishing flow, and Kubernetes manifests exist
- unit and integration tests exist for actions, incident persistence, HTTP routes, and Telegram command handling

### Recent Fixes Reflected In Code

- model selection is configurable through environment variables in `model_factory.py`
- FastAPI response typing now accepts structured incident payloads
- Telegram long polling no longer times out prematurely because the HTTP timeout is longer than the poll timeout
- deployment manifest now includes a startup probe so startup latency does not trigger liveness restarts prematurely
- deployment docs now include Telegram polling configuration knobs in both runtime env guidance and Kubernetes secret setup
- the testing-only CLI command surface has been removed
- reject handling now preserves terminal action states and marks expired actions consistently
- integration coverage now includes an alertmanager webhook -> pending action -> approval execution path with incident/action linkage validation

## What Still Needs Real Validation

These are code-complete or mostly code-complete, but still need live proof:

- full alert -> investigate -> propose -> notify -> approve -> execute flow in a real cluster
- Telegram polling and approval behavior in the deployed pod, not just locally
- model behavior on real incidents: whether it proposes the expected actions consistently
- write RBAC coverage for the currently supported guarded actions in-cluster

## Highest-Value Next Steps

### 1. Run One Real End-To-End Validation

- deploy the current service to a dev or kind cluster
- send a real Alertmanager-style payload
- confirm the agent creates at least one pending action
- confirm Telegram receives the incident with action IDs
- approve from Telegram
- confirm the action executes and the cluster state changes as expected

Goal:
- prove the product loop works outside tests and local mocks

### 2. Tighten The HTTP And Telegram Contract

- add explicit response models for incidents and health responses
- normalize the incident payload shape so HTTP, store, and Telegram all use the same fields
- make Telegram error replies more operator-friendly

Goal:
- reduce ambiguity in service behavior and make future refactors safer

### 3. Replace Ad Hoc Persistence With A Clear Store Layer

- keep the current JSON stores for local development
- define a cleaner abstraction for incidents and actions
- prepare for a future Redis or database-backed implementation if needed

Goal:
- make persistence easier to reason about and easier to replace

### 4. Strengthen Runtime Safety

- improve operator-facing error formatting consistency between HTTP and Telegram responses
- verify write actions fail closed in all unsupported cases
- review whether `scale` and `rollout-undo` need additional target validation

Goal:
- make the action path operationally safer before broader usage

### 5. Improve Deployment Readiness

- verify secret configuration and env docs against the current deployment manifests
- verify probe behavior and startup timing in-cluster

Goal:
- reduce surprises when the service is deployed as a long-running pod

## Medium-Term Cleanup

### 6. Introduce Typed Models For Incidents And Actions

- replace loosely typed dict payloads with explicit Pydantic models or dataclasses
- use those models across HTTP, Telegram, store, and notifier paths

Goal:
- reduce bugs caused by payload-shape drift

### 7. Refine The File Layout Further

- keep the current `app/` structure
- consider pulling incident formatting, Telegram message formatting, and response shaping into smaller dedicated modules

Goal:
- make the codebase easier to review as the service grows

### 8. Expand Test Coverage Around Live Edge Cases

- add tests for long-poll timeout configuration
- add tests for action execution failures and retry-safe approval behavior beyond the current webhook-to-approve coverage
- add tests for unauthorized Telegram chats and expired actions in the service path

Goal:
- cover the failure modes most likely to break operator trust

## Documentation Work

### 9. Keep `TESTING.md` Current

- keep it short
- keep it focused on the current service-first flow
- avoid reintroducing historical CLI workflows

Goal:
- make validation instructions match the actual product shape

### 10. Keep `README.md` Aligned With Runtime Reality

- keep FastAPI as the primary interface in the docs
- keep Telegram documented as a complementary interface
- keep the architecture diagram updated when core component flow changes

Goal:
- ensure new readers understand the current architecture without reading the whole codebase
