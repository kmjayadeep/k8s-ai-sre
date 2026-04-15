# Testing Guide

Use this file as the current runbook. It intentionally keeps only a few representative flows. If you are starting from a contributor task, use [docs/contributing.md](docs/contributing.md) to choose the right lane first, [docs/testing.md](docs/testing.md) to match change type to validation depth, and [docs/developer.md](docs/developer.md) for local setup and request examples.

## Prerequisites

- a working kube context, ideally a local kind cluster
- model credentials loaded in the shell (`MODEL_NAME` and `MODEL_API_KEY`)
- write allow-list configured in the shell (`WRITE_ALLOWED_NAMESPACES`, non-empty)
- Telegram credentials loaded in the shell for notification/command flow (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALLOWED_CHAT_IDS`)
- optional HTTP operator token for non-interactive approvals (`OPERATOR_API_TOKEN`)
- optional SQLite store path override (`K8S_AI_SRE_STORE_PATH`)

Useful checks:

```bash
kubectl config current-context
kubectl get nodes
scripts/baseline.sh
```

CI (`.github/workflows/tests.yml`) now runs a two-stage pipeline:

- `scripts/smoke.sh` for fast critical path checks
- `scripts/baseline.sh` as the authoritative full test path

The full job still calls `scripts/baseline.sh` so local and CI correctness stay aligned while smoke shortens first failure feedback.

`scripts/smoke.sh` currently executes:

```bash
uv run python -m unittest \
  tests.test_ci_smoke_api_contract \
  tests.test_ci_smoke_alert_approval_loop
```

This smoke lane validates a deterministic alertmanager -> incident -> proposal -> token-guarded approve/reject loop and contract-level response keys without requiring Telegram or Kubernetes.

Local equivalent timing snapshot (2026-04-13):

- baseline-only path: `scripts/baseline.sh` -> `2.160s`
- smoke first signal: `scripts/smoke.sh` -> `1.991s`
- first feedback improvement: `0.169s` faster (~7.8%) before full baseline starts

Telegram timeout safety is covered by unit tests (`tests/test_telegram_commands.py`) and verifies poll/HTTP timeout guardrails.

## CI Manifest Gate (Helm + Kustomize)

Run the same commands as CI when changing Helm chart or deploy manifests:

```bash
helm lint chart
helm template k8s-ai-sre ./chart --namespace ai-sre-system > /tmp/chart-rendered.yaml
kustomize build deploy > /tmp/deploy-rendered.yaml
kubeconform -strict -summary -ignore-missing-schemas /tmp/chart-rendered.yaml
kubeconform -strict -summary -ignore-missing-schemas /tmp/deploy-rendered.yaml
```

## Example 1: Local Service And Investigation

Create the demo namespace and a broken deployment:

```bash
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f examples/kind-bad-deploy.yaml
```

Start the service:

```bash
uv run main.py
```

Trigger an investigation:

```bash
curl -X POST http://127.0.0.1:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"bad-deploy"}'
```

What to verify:

- the response includes `incident_id`
- the response includes `source` (`manual` for `/investigate`, `alertmanager` for webhook flow)
- the response includes `answer`
- the response includes `action_ids` and `proposed_actions`; when the model skips proposals, deployment/pod targets now receive deterministic fallback proposals
- `http://127.0.0.1:8080/` shows an incident feed and renders incident details after selection

## Example 2: Local Server And Webhook

Start the HTTP service:

```bash
uv run main.py
```

In another terminal, send an Alertmanager-style payload:

```bash
curl -X POST http://127.0.0.1:8080/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  --data @examples/alertmanager-bad-deploy.json
```

What to verify:

- the response includes `incident_id`
- the response includes `source` with value `alertmanager`
- the response includes `answer`
- the response includes `action_ids` and `proposed_actions`; when the model skips proposals, deployment/pod targets now receive deterministic fallback proposals
- the response includes `notification_status`

Fetch the stored incident:

```bash
curl http://127.0.0.1:8080/incidents/<incident-id>
```

## Example 3: Telegram Approval Flow

Required environment:

```bash
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
export TELEGRAM_ALLOWED_CHAT_IDS=...
```

Optional non-Telegram automation path:

```bash
export OPERATOR_API_TOKEN=...
```

Optional polling overrides:

```bash
export TELEGRAM_POLL_ENABLED=true
export TELEGRAM_POLL_TIMEOUT_SECONDS=30
export TELEGRAM_HTTP_TIMEOUT_SECONDS=35
export TELEGRAM_POLL_INTERVAL_SECONDS=1
export TELEGRAM_POLL_BACKOFF_SECONDS=5
```

Create an incident through `/investigate` or `/webhooks/alertmanager`.

The server polls Telegram automatically when `TELEGRAM_BOT_TOKEN` is configured.

From Telegram:

```text
/incident <incident-id>
/status <incident-id>
/approve <action-id>
/reject <action-id>
```

Notification messages also include inline `Approve <action-id>` / `Reject <action-id>` buttons for one-tap decisions.

What to verify:

- incident messages show action IDs when proposals exist
- incident messages include inline Approve/Reject buttons for proposed actions
- `/approve` executes the guarded action
- `/reject` updates the action state without execution
- missing command arguments return a clear usage hint (for example `/approve` -> `Usage: /approve <action-id>`)
- when `OPERATOR_API_TOKEN` is set, `POST /actions/<action-id>/approve` and `POST /actions/<action-id>/reject` require both `Authorization: Bearer <token>` and `X-Operator-Id: <operator-id>` and update action state without Telegram input
- `GET /metrics` exposes loop-health metrics including investigation latency, proposal totals, approval latency, and action execution outcomes
- HTTP approval validation errors expose structured detail shape: `{"code":"...","message":"..."}`
- Telegram command/callback internal failures include taxonomy prefixes in operator replies (for example `[telegram_command_execution_failed] ...`)

## Example 4: Kind End-To-End Exercise

Preferred workflow for repeatable heartbeats:

1. build a local image
2. load it into kind
3. deploy into `ai-sre-system` using the existing `k8s-ai-sre-env` secret
4. port-forward the in-cluster service and run the webhook

```bash
docker build -t k8s-ai-sre:e2e .
kind load docker-image k8s-ai-sre:e2e --name k8s-ai-sre
kubectl apply -k deploy
kubectl -n ai-sre-system set image deployment/k8s-ai-sre app=k8s-ai-sre:e2e
kubectl -n ai-sre-system patch deployment k8s-ai-sre --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]'
kubectl -n ai-sre-system rollout status deployment/k8s-ai-sre
kubectl -n ai-sre-system port-forward svc/k8s-ai-sre 18080:80
```

Then send an Alertmanager-style payload:

```bash
curl -X POST http://127.0.0.1:18080/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  --data @examples/alertmanager-bad-deploy.json
```

The repository includes helper scripts:

```bash
scripts/e2e_kind.sh
scripts/e2e_full_stack_kind.sh
```

`scripts/e2e_kind.sh` will:

- fail fast if model or Telegram credentials are missing
- apply the broken deployment scenario
- prompt you to start the service locally or port-forward the in-cluster service
- send the sample Alertmanager payload
- save the incident response to `/tmp/k8s-ai-sre-e2e-incident.json`

What to verify:

- the incident response contains `incident_id` and any proposed `action_ids`
- Telegram receives the notification
- approving an action from Telegram changes cluster state as expected
- or, for automation, approve through HTTP:

```bash
ACTION_ID="$(jq -r '.action_ids[0]' /tmp/k8s-ai-sre-e2e-incident.json)"
curl -X POST "http://127.0.0.1:18080/actions/${ACTION_ID}/approve" \
  -H "Authorization: Bearer ${OPERATOR_API_TOKEN}" \
  -H "X-Operator-Id: ci-e2e"
```

Note:
- if logs repeatedly show `telegram_poll_loop_failed` with `HTTP Error 409: Conflict`, another process is already consuming `getUpdates` for that bot token; use a dedicated bot token (or stop the competing consumer) before relying on Telegram polling validation.
- do not use bot-token `sendMessage` to emulate operator approval; bot-originated messages are not ingested as incoming command updates for the same bot. Use a real Telegram user chat message for `/approve` validation.
- for repeatable CI-like checks, prefer the token-guarded HTTP operator endpoint instead of bot-originated Telegram messages.

## Example 5: Full Alert Pipeline In Kind (Prometheus + Alertmanager)

This verifies that a real in-cluster alert (not a synthetic webhook curl) drives the full loop.

Prerequisites:

- `kind`, `kubectl`, `docker`, `jq`, `curl` (`helm` is used if installed; otherwise the script downloads a local Helm binary)
- model credentials (`MODEL_NAME` and `MODEL_API_KEY`)
- Telegram credentials (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALLOWED_CHAT_IDS`)
- operator API token (`OPERATOR_API_TOKEN`) for non-interactive approval
- optional operator identity header value (`OPERATOR_ID`, default: `e2e-kind-runner`)
- alternatively, pre-existing `ai-sre-system/k8s-ai-sre-env` secret with those keys; the script backfills missing shell vars from that secret

Run:

```bash
scripts/e2e_full_stack_kind.sh
```

What it does:

- builds and loads `k8s-ai-sre:e2e` into kind
- deploys app manifests into `ai-sre-system`
- installs `kube-prometheus-stack` in `monitoring` using `examples/monitoring/kube-prom-stack-values.yaml`
- applies `examples/monitoring/bad-deploy-prometheus-rule.yaml`
- creates the failing `bad-deploy` workload in `ai-sre-demo`
- waits for `DeploymentReplicasUnavailable` in Alertmanager
- waits for a `source=alertmanager` incident in `/incidents`
- approves first proposed action via `POST /actions/{id}/approve`
- verifies the action reaches a terminal execution state and records workload health as best-effort context
- writes evidence bundle to `/tmp/k8s-ai-sre-aie30/`

Important:

- if the model returns no proposed actions (`action_ids=[]`), the script exits non-zero after saving evidence and a `failure-reason.txt`; this indicates a real propose-stage gap.

Expected evidence:

- `/tmp/k8s-ai-sre-aie30/incidents.json`
- `/tmp/k8s-ai-sre-aie30/alertmanager-alerts.json`
- `/tmp/k8s-ai-sre-aie30/approval.json`
- `/tmp/k8s-ai-sre-aie30/execution-summary.json`
- `/tmp/k8s-ai-sre-aie30/bad-deploy-state.yaml`
- `/tmp/k8s-ai-sre-aie30/bad-deploy-pods.txt`

## Example 6: Reliability Evidence Bundle (N>=5 runs)

Use this when validating the P0 reliability gate (`alert -> investigate -> propose -> notify -> approve -> execute`) with repeatability and artifacts.

Required environment:

```bash
export OPERATOR_API_TOKEN=...
```

Recommended (service in cluster):

```bash
RUNS=5 scripts/e2e_reliability_kind.sh
```

What this script does:

- runs the alertmanager flow repeatedly (`RUNS`, default `5`)
- auto-approves the first proposed action through `POST /actions/{action_id}/approve`
- retries approval immediately and once more after restarting the in-cluster service deployment to verify idempotent terminal behavior
- captures per-run evidence under `/tmp/k8s-ai-sre-reliability/<timestamp>/run-XX/`
- writes aggregate summaries to:
  - `/tmp/k8s-ai-sre-reliability/<timestamp>/summary.json`
  - `/tmp/k8s-ai-sre-reliability/<timestamp>/summary.tsv`

Each run captures:

- `webhook-response.json` (incident + action IDs)
- `incident-readback.json`
- `approval-first.json`, `approval-retry.json`, and `approval-post-restart-retry.json`
- `cluster-before.txt`, `cluster-after.txt`, and `cluster-diff.txt`
- `service.log` and run-level `summary.json`

Exit behavior:

- exits `0` only when all runs succeed and status is stable across retries/restart
- exits non-zero if any run fails, action IDs are missing (default), or status diverges between first approval and retries

Useful toggles:

```bash
RUNS=7 RUN_RESTART_CHECK=0 scripts/e2e_reliability_kind.sh
REQUIRE_ACTION_ID=0 scripts/e2e_reliability_kind.sh
AUTO_PORT_FORWARD=0 SERVICE_URL=http://127.0.0.1:8080 scripts/e2e_reliability_kind.sh
```

## Cleanup

```bash
kubectl delete -f examples/kind-bad-deploy.yaml --ignore-not-found
kubectl delete namespace ai-sre-demo --ignore-not-found
rm -f /tmp/k8s-ai-sre-store.sqlite3 /tmp/k8s-ai-sre-actions.json /tmp/k8s-ai-sre-incidents.json /tmp/k8s-ai-sre-e2e-incident.json
rm -rf /tmp/k8s-ai-sre-aie30
rm -rf /tmp/k8s-ai-sre-reliability
```
