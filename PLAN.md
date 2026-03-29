# k8s-ai-sre Plan

## Goal

Finish the project as a working end-to-end AI Kubernetes SRE flow:

1. Alert arrives.
2. Agent investigates with real cluster evidence.
3. Agent proposes guarded remediation actions as pending approvals.
4. User approves or rejects from Telegram.
5. Approved action executes through the existing guardrails.

## Current Status

### Already Done

- Real `kubectl`-backed Kubernetes reads are in place.
- Generic resource lookup works for built-ins and CRD-shaped access patterns.
- Evidence collection includes resource details, events, workload pods, logs, and optional Prometheus data.
- The agent synthesizes evidence into an investigation answer.
- Guarded write actions exist for `delete-pod`, `rollout-restart`, `scale`, and `rollout-undo`.
- Local action approval storage exists with expiry handling.
- FastAPI service exists with `/healthz`, `/investigate`, `/webhooks/alertmanager`, and `/incidents/{id}`.
- Alertmanager webhooks trigger investigations.
- Incident state is persisted in a local JSON store.
- Telegram notifications are sent for incidents.
- Telegram supports `/incident`, `/status`, `/approve`, and `/reject`.
- Write namespaces and allowed Telegram chat IDs can be restricted.
- Structured logging is in place.
- Container build, GHCR publishing, and Kubernetes deployment manifests are in place.

### Not Done Yet

- The agent cannot create pending actions itself.
- Proposed actions are only plain text in the investigation answer.
- Incidents do not store structured action proposals.
- Telegram notifications do not include agent-generated action IDs.
- Telegram approval only works for actions created manually through the CLI.
- The full alert -> investigate -> propose -> notify -> approve -> execute loop is not complete.

## Design Rules

- Keep the model read-only with respect to execution.
- Give the model proposal tools, not execution tools.
- Keep approval and execution outside the model.
- Prefer generic Kubernetes resource access where possible.
- Keep each new step locally testable before moving on.

## Next Steps

### 1. Refactor File Structure

- Reduce the current ad hoc module layout into clearer boundaries such as:
  - `app/investigate.py`
  - `app/actions.py`
  - `app/store.py`
  - `app/telegram.py`
  - `app/http.py`
  - `app/tools/k8s.py`
  - `app/tools/actions.py`
- Keep the refactor small and mechanical.

Goal:
- make the codebase easier to navigate before adding more features

### 2. Refactor CLI Logic

- Move CLI argument handling out of `main.py`.
- Decide whether the manual CLI action commands should remain.
- Once tests cover the behavior, consider removing most of the manual CLI approval commands if they are no longer needed.

Goal:
- stop using `main.py` as the central control plane

### 3. Add Agent Proposal Tools

- Add tool functions for:
  - `propose_delete_pod(namespace, pod_name)`
  - `propose_rollout_restart(namespace, deployment_name)`
  - `propose_scale(namespace, deployment_name, replicas)`
  - `propose_rollout_undo(namespace, deployment_name)`
- Each tool should create a pending action in `action_store.py`.
- Each tool should return structured approval details:
  - action ID
  - target
  - params
  - expiry
  - approval and rejection commands

Goal:
- let the LLM propose real guarded actions without executing them

### 4. Update Agent Prompt And Result Contract

- Change the prompt so the agent investigates first and proposes actions through tools when justified.
- Stop relying on plain-text “Proposed actions” only.
- Make the final answer reference concrete action IDs when proposals exist.

Goal:
- make the LLM output actionable and traceable

### 5. Persist Structured Proposed Actions In Incidents

- Extend incident records with:
  - `proposed_actions`
  - `action_ids`
- Tie each created action to an `incident_id`.

Goal:
- allow later retrieval and approval from incident context

### 6. Improve Telegram Incident Notifications

- Include proposed action IDs in the initial Telegram message.
- Include approval instructions in the message.
- Keep the message concise and operator-friendly.

Goal:
- make the operator able to act directly from the incident notification

### 7. Improve Telegram Incident Views

- Update `/incident <id>` and `/status <id>` to show pending actions tied to the incident.
- Make approval and rejection messages include the originating incident when available.

Goal:
- make Telegram the real approval surface for agent-proposed actions

### 8. Verify The Full End-To-End Flow

- Trigger a sample Alertmanager webhook.
- Confirm the investigation runs.
- Confirm the agent creates at least one pending action through a proposal tool.
- Confirm the incident record stores the proposed action.
- Confirm Telegram notification includes the action ID.
- Approve the action from Telegram.
- Confirm the action executes and status updates correctly.

Goal:
- prove the core product loop actually works

## Cleanup And Hardening After The Core Loop Works

### 9. Add Tests

- Add unit tests for:
  - action proposal creation
  - incident persistence with action IDs
  - Telegram command formatting
  - approval and expiry behavior
- Add HTTP tests for:
  - `/investigate`
  - `/webhooks/alertmanager`
  - `/incidents/{id}`

Goal:
- cover the core control flow before more refactors

### 10. Add Integration Tests

- Add integration-style tests around:
  - alert ingestion
  - investigation result persistence
  - Telegram message formatting
  - action approval flow
- Mock `kubectl`, Telegram API, and model calls where needed.

Goal:
- verify module interaction, not just isolated functions

### 11. Run A Real Full End-To-End Test

- Use kind.
- Deploy the app.
- Send a real webhook payload.
- Confirm Telegram notification.
- Approve from Telegram.
- Confirm the Kubernetes action runs.

Goal:
- validate production-like behavior, not just local mocks

### 12. Rewrite `TESTING.md`

- Replace the long historical checklist with a few short, current examples:
  - local investigation
  - local server + webhook
  - Telegram approval flow
  - in-cluster deploy smoke test

Goal:
- make testing instructions usable by humans

### 13. Rewrite `README.md`

- Add a short project overview.
- Add a quick start for new users.
- Add a minimal local run path.
- Add a minimal kind deploy path.
- Link to `TESTING.md` for deeper verification instead of duplicating too much detail.

Goal:
- make the repo understandable to a new reader in a few minutes
