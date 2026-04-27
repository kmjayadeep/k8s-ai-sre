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

Investigation endpoints (`/investigate`, `/webhooks/alertmanager`) and incident queries (`GET /incidents`, `GET /incidents/<id>`) return normalized incident payloads.

### IncidentResponse

| Field | Type | Description |
|---|---|---|
| `incident_id` | string | Unique identifier |
| `kind` | string | Kubernetes resource kind (e.g., `deployment`, `statefulset`) |
| `namespace` | string | Namespace of the affected resource |
| `name` | string | Name of the affected resource |
| `lifecycle_status` | string | `active` or `resolved` |
| `source` | string | Origin: `manual` or `alertmanager` |
| `created_at` | string | ISO timestamp when the incident was created |
| `updated_at` | string | ISO timestamp of the most recent event |
| `last_event_at` | string | ISO timestamp of the most recent event |
| `answer` | string | LLM investigation summary and proposed cause |
| `evidence` | string | Raw evidence collected during investigation |
| `brief` | object | Structured summary with `summary`, `root_cause`, `confidence`, `action_items` |
| `action_ids` | string[] | List of action identifiers pending approval |
| `proposed_actions` | object[] | Proposed actions with `action_id`, `action_type`, `namespace`, `name`, `approve_command`, `reject_command` |
| `notification_status` | string | Notification delivery status |
| `dedup_key` | string | Deduplication key for grouping related alerts |
| `dedup_count` | int | Number of deduplicated alerts |
| `event_history` | object[] | Timeline events with `event`, `source`, `occurred_at`, `details` |
| `supersedes_incident_id` | string | ID of the incident this one supersedes |
| `related_incident_ids` | string[] | IDs of related incidents |

### IncidentsResponse

| Field | Type | Description |
|---|---|---|
| `incidents` | IncidentResponse[] | List of all incidents |

## Incident Inspector UI

The incident inspector is a browser-based UI at the root path (`/`) that provides real-time visibility into incident state and lifecycle.

### Accessing the UI

Navigate to the service root URL. For local development: `http://127.0.0.1:8080/`

Authentication is enforced via `INSPECTOR_BASIC_AUTH`. Configure with `operator:secret` style format.

### UI Layout

The UI is split into two panels:

**Incident Feed (left panel)**

- Displays all targets affected by incidents
- Groups incidents by target (`kind/namespace/name`)
- Shows one row per target with the latest incident's status
- Click a row to inspect that target's timeline

**Incident Inspector (right panel)**

When a target is selected, displays four cards:

1. **Target Overview**: Target identity, latest incident ID, lifecycle status, source, timestamps, notification status, and linked incident IDs
2. **Latest Investigation Summary**: The `answer` field from the most recent incident for the target
3. **Latest Proposed Actions**: Proposed actions with approve/reject commands for the most recent incident
4. **Incident Timeline**: Chronological event history including all incident state transitions and events

### Key UI Behaviors

- **Grouping**: Incidents are grouped by target, showing all linked incidents for the same resource
- **Timeline**: Each incident shows its creation/update timestamps and full event history
- **Lifecycle**: Active incidents show green status; resolved incidents show gray
- **Actions**: Each proposed action includes copy-pasteable `approve` and `reject` commands

### Data Source

The UI fetches from `GET /incidents`, which returns all incidents from the store. The UI processes this client-side to group by target and render timelines.

For programmatic access, use `GET /incidents` and `GET /incidents/{incident_id}` directly.
