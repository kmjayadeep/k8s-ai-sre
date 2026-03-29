# k8s-ai-sre

`k8s-ai-sre` is an AI-assisted Kubernetes incident investigator with guarded remediation.

Today it can:

- investigate pods and deployments with real `kubectl` reads
- collect evidence from resource state, events, logs, and optional Prometheus queries
- accept Alertmanager-style webhooks
- persist incidents and pending actions locally
- notify and approve actions through Telegram
- execute guarded actions only after explicit approval

The intended loop is:

1. an alert or manual request targets a Kubernetes object
2. the agent gathers evidence and explains the likely cause
3. the agent can create pending remediation proposals
4. an operator approves or rejects those proposals
5. approved actions execute through the existing guardrails

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Load Environment

At minimum, load your model credentials. Telegram is optional for the local CLI flow.

Typical local variables:

```bash
export PORTKEY_API_KEY=...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
export TELEGRAM_ALLOWED_CHAT_IDS=...
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo
```

### 3. Prepare A Local Scenario

```bash
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f examples/kind-bad-deploy.yaml
```

### 4. Run A Local Investigation

```bash
uv run main.py deployment ai-sre-demo bad-deploy
```

### 5. Run The HTTP Service

```bash
uv run main.py serve
```

Then send a sample webhook:

```bash
curl -X POST http://127.0.0.1:8080/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  --data @examples/alertmanager-bad-deploy.json
```

## Telegram Flow

Telegram is optional for investigation but required for the chat approval loop.

Once the bot token and chat IDs are configured, you can:

- receive incident notifications
- fetch incident details with `/incident <incident-id>`
- check status with `/status <incident-id>`
- approve actions with `/approve <action-id>`
- reject actions with `/reject <action-id>`

To poll Telegram updates locally:

```bash
uv run main.py telegram-poll
```

## Guarded Actions

The current guarded actions are:

- `delete-pod`
- `rollout-restart`
- `scale`
- `rollout-undo`

They are namespace-restricted through `WRITE_ALLOWED_NAMESPACES` and require explicit approval before execution.

## Deployment

The repository includes a Kustomize base in [deploy](deploy) and publishes a container image to:

```text
ghcr.io/kmjayadeep/k8s-ai-sre:main
```

Create the runtime secret:

```bash
kubectl create namespace ai-sre-system --dry-run=client -o yaml | kubectl apply -f -
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=PORTKEY_API_KEY="$PORTKEY_API_KEY" \
  --from-literal=TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
  --from-literal=TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
  --from-literal=TELEGRAM_ALLOWED_CHAT_IDS="$TELEGRAM_ALLOWED_CHAT_IDS" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="$WRITE_ALLOWED_NAMESPACES" \
  --dry-run=client -o yaml | kubectl apply -f -
```

Deploy:

```bash
kubectl apply -k deploy
kubectl get pods -n ai-sre-system
kubectl get svc -n ai-sre-system
```

The in-cluster runtime still uses `kubectl`, backed by the pod service account and the provided RBAC.

## Repo Map

- [main.py](main.py): entrypoint
- [app/investigate.py](app/investigate.py): agent construction and investigation flow
- [app/http.py](app/http.py): FastAPI endpoints
- [app/telegram.py](app/telegram.py): Telegram polling and commands
- [app/actions.py](app/actions.py): proposal and approval orchestration
- [app/tools/k8s.py](app/tools/k8s.py): Kubernetes and Prometheus read tools
- [app/tools/actions.py](app/tools/actions.py): guarded action execution
- [app/stores](app/stores): local JSON stores for incidents and actions

## Testing

See [TESTING.md](TESTING.md) for the current concise runbook:

- local investigation
- local server plus webhook
- Telegram approval flow
- live kind end-to-end exercise
