# Testing Guide

Use this file as the current runbook. It intentionally keeps only a few representative flows.

## Prerequisites

- a working kube context, ideally a local kind cluster
- model credentials loaded in the shell
- optional Telegram credentials if you want the chat flow

Useful checks:

```bash
kubectl config current-context
kubectl get nodes
.venv/bin/python -m unittest discover -s tests
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
- the response includes `answer`
- the response includes `action_ids` and `proposed_actions` when the model used proposal tools

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
- the response includes `answer`
- the response includes `action_ids` and `proposed_actions` when the model used proposal tools
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

Create an incident through `/investigate` or `/webhooks/alertmanager`.

The server polls Telegram automatically when `TELEGRAM_BOT_TOKEN` is configured.

From Telegram:

```text
/incident <incident-id>
/status <incident-id>
/approve <action-id>
/reject <action-id>
```

What to verify:

- incident messages show action IDs when proposals exist
- `/approve` executes the guarded action
- `/reject` updates the action state without execution

## Example 4: Kind End-To-End Exercise

The repository includes a live helper script:

```bash
scripts/e2e_kind.sh
```

It will:

- apply the broken deployment scenario
- prompt you to start the service locally or port-forward the in-cluster service
- send the sample Alertmanager payload
- save the incident response to `/tmp/k8s-ai-sre-e2e-incident.json`

What to verify:

- the incident response contains `incident_id` and any proposed `action_ids`
- Telegram receives the notification
- approving an action from Telegram changes cluster state as expected

## Latest Validation Evidence (2026-04-01)

Environment execution in this run:

```bash
kind create cluster --name ai-sre --wait 120s
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k deploy
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=MODEL_API_KEY=dummy \
  --from-literal=MODEL_NAME=openai/gpt-oss-20b \
  --from-literal=MODEL_PROVIDER=groq \
  --from-literal=MODEL_BASE_URL=https://api.portkey.ai/v1 \
  --from-literal=WRITE_ALLOWED_NAMESPACES=ai-sre-demo \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n ai-sre-system rollout restart deploy/k8s-ai-sre
kubectl -n ai-sre-system port-forward svc/k8s-ai-sre 18080:80
curl http://127.0.0.1:18080/healthz
curl -X POST http://127.0.0.1:18080/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  --data @examples/alertmanager-bad-deploy.json
```

Observed results:

- `/healthz` returned `200 {"status":"ok"}`.
- `/webhooks/alertmanager` returned `500 Internal Server Error`.
- Pod logs showed `telegram_poll_not_started` with `reason: token_missing`.
- Pod logs showed model call failure: `openai.AuthenticationError ... Invalid API Key ... Error Code: 03`.

Blocking inputs for full `alert -> investigate -> propose -> notify -> approve -> execute` validation:

- a valid `PORTKEY_API_KEY` or `MODEL_API_KEY`
- Telegram runtime credentials: `TELEGRAM_BOT_TOKEN` and allowed chat configuration

## Cleanup

```bash
kubectl delete -f examples/kind-bad-deploy.yaml --ignore-not-found
kubectl delete namespace ai-sre-demo --ignore-not-found
rm -f /tmp/k8s-ai-sre-actions.json /tmp/k8s-ai-sre-incidents.json /tmp/k8s-ai-sre-e2e-incident.json
```
