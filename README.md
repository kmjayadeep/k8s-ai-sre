# k8s-ai-sre

> AI-powered incident response for Kubernetes. Investigate, propose, approve, execute.

Stop spending hours debugging production issues. `k8s-ai-sre` gives you a AI co-pilot that:

- 🔍 **Investigates** - Gathers real cluster evidence: pod logs, events, deployments, metrics
- 🤖 **Proposes** - Suggests concrete remediation steps based on evidence
- ✅ **Guards** - Every action requires explicit operator approval
- 🔒 **Protects** - Namespace allowlists, kubectl auth checks, audit logging

## Quick Start

```bash
# 1. Install
uv sync

# 2. Configure
export MODEL_API_KEY=your-key
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.groq.com/openai/v1
export MODEL_NAME=openai/gpt-oss-20b
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo

# 3. Run
uv run main.py

# 4. Investigate
curl -X POST http://127.0.0.1:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"bad-deploy"}'
```

## How It Works

```
Alert → Investigate → Propose → Approve → Execute
          ↓
    kubectl get pods
    kubectl logs
    kubectl events
    kubectl describe
```

1. **Alert arrives** via HTTP or Alertmanager webhook
2. **Investigation runs** - queries pods, logs, events, metrics
3. **Proposals created** - concrete actions with `/approve` commands
4. **You decide** - Telegram or HTTP API approval
5. **Action executes** - only after explicit approval

## Features

- **Multiple input channels**: HTTP API, Alertmanager webhooks
- **Telegram integration**: Get notified, approve/reject from your phone
- **Guardrails built-in**: Namespace allowlists, auth checks, audit trail
- **Prometheus metrics**: Monitor investigation latency, approval times, success rates

## Telegram Commands

```
/incident <id>    - Get incident details
/status <id>      - Check action status
/approve <id>    - Approve an action
/reject <id>      - Reject an action
```

## Supported Actions

| Action | Description |
|--------|-------------|
| `delete-pod` | Delete a stuck pod (allows kubelet to restart) |
| `rollout-restart` | Restart a deployment |
| `scale` | Adjust replica count |
| `rollout-undo` | Undo a deployment rollout |

## Deployment

```bash
# Create namespace and secret
kubectl create namespace ai-sre-system
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=MODEL_API_KEY="$MODEL_API_KEY" \
  --from-literal=MODEL_NAME="$MODEL_NAME" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="$WRITE_ALLOWED_NAMESPACES"

# Deploy
kubectl apply -k deploy
```

Image: `ghcr.io/kmjayadeep/k8s-ai-sre:main`

## Documentation

- [Quick Start](docs/quickstart.md)
- [Deployment Guide](docs/deployment.md)
- [Testing Guide](TESTING.md)
- [Portkey Integration](docs/portkey.md)

## License

MIT
