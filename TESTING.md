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
- missing command arguments return explicit `Usage: ...` replies (for example `/approve` without an action ID)

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

## Cleanup

```bash
kubectl delete -f examples/kind-bad-deploy.yaml --ignore-not-found
kubectl delete namespace ai-sre-demo --ignore-not-found
rm -f /tmp/k8s-ai-sre-actions.json /tmp/k8s-ai-sre-incidents.json /tmp/k8s-ai-sre-e2e-incident.json
```
