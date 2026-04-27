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

Investigation endpoints (`/investigate`, `/webhooks/alertmanager`) and incident queries (`GET /incidents`, `GET /incidents/<id>`) return normalized incident payloads with these fields:

| Field | Description |
|---|---|
| `incident_id` | Unique identifier |
| `source` | Origin: `manual` or `alertmanager` |
| `lifecycle_status` | `active` or `resolved` |
| `created_at` | ISO timestamp when the incident was created |
| `updated_at` | ISO timestamp of the most recent event |
| `answer` | LLM investigation summary and proposed cause |
| `action_ids` | List of action identifiers pending approval |
| `proposed_actions` | Array of `{id, description, kubectl_command}` objects |

Query `/incidents` returns an array. The incident inspector UI at `app/ui/incident_inspector.html` renders grouped timelines — one row per target with all linked incidents and lifecycle metadata expanded inline.
