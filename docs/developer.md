# Developer Guide

Use this page for local setup and command reference. If you are new to the repo workflow, start with [Contributing](contributing.md). For first-time product setup, start with `docs/quickstart.md`. For validation depth, use [Validation guide](testing.md).

## Local Development

### Install dependencies

```bash
uv sync
```

### Configure model access

Required:

```bash
export MODEL_NAME=openai/gpt-oss-20b
export MODEL_API_KEY=your-api-key
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.groq.com/openai/v1
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo
```

Portkey remains a supported gateway. Point `MODEL_BASE_URL` at Portkey and keep `MODEL_PROVIDER` set to the provider label you want recorded in traces.

### Create demo scenario

```bash
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f examples/kind-bad-deploy.yaml
```

### Start the service

```bash
uv run main.py
```

### Trigger investigation

Manual endpoint:

```bash
curl -X POST http://127.0.0.1:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"bad-deploy"}'
```

Alertmanager-style webhook:

```bash
curl -X POST http://127.0.0.1:8080/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  --data @examples/alertmanager-bad-deploy.json
```

## Related Workflow Docs

- [Contributing](contributing.md) owns the contributor path, PR handoff, and merge ownership.
- [Validation guide](testing.md) helps you choose the right validation lane for a change.
- [Repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md) contains the full validation sequences and end-to-end flows.

## Expected Response Fields

Investigation creation endpoints return normalized incident payloads including:

- `incident_id`
- `source`
- `answer`
- `action_ids`
- `proposed_actions`
