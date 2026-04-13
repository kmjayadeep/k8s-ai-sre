# k8s-ai-sre

> AI-powered incident response for Kubernetes. Investigate, propose, approve, execute.

Stop spending hours debugging production. `k8s-ai-sre` is an AI co-pilot that investigates cluster incidents, proposes concrete remediation steps, and executes them only after you explicitly approve — with guardrails in place.

---

## The Loop

```
Alert → Investigate → Propose → Approve → Execute
         ↓
   kubectl get pods
   kubectl logs
   kubectl describe
   kubectl events
```

1. **Alert arrives** via HTTP API or Alertmanager webhook
2. **AI investigates** — gathers real evidence: pod logs, events, resource metrics
3. **Proposals created** — concrete actions with Telegram approval commands
4. **You decide** — approve or reject from Telegram or the HTTP API
5. **Action executes** — only after explicit approval, with namespace/auth guardrails

---

## Quick Start

```bash
# 1. Install
uv sync

# 2. Configure
export MODEL_API_KEY=***
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.groq.com/openai/v1
export MODEL_NAME=openai/gpt-oss-20b
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo

# 3. Run
uv run main.py

# 4. Investigate
curl -X POST http://127.0.0.1:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"my-deploy"}'
```

Or trigger via Alertmanager — see the [Quick Start guide](docs/quickstart.md).

---

## Features

| | |
|---|---|
| **Multiple input channels** | HTTP API, Alertmanager webhooks |
| **Telegram integration** | Approve/reject incidents from your phone |
| **Guardrails built-in** | Namespace allowlists, kubectl auth checks, audit trail |
| **Prometheus metrics** | Investigation latency, approval times, action success rates |
| **Deterministic fallbacks** | Proposes safe recovery even if model skips a tool call |

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/incident <id>` | Get incident details and proposed actions |
| `/status <id>` | Check action execution status |
| `/approve <id>` | Approve an action for execution |
| `/reject <id>` | Reject and discard an action |

---

## Supported Actions

| Action | When to Use |
|--------|-------------|
| `delete-pod` | Pod stuck in CrashLoopBackOff or Pending — kubelet will restart |
| `rollout-restart` | Deployment needs a fresh start without changing config |
| `scale` | Replica count too low or too high |
| `rollout-undo` | Bad deployment — roll back to the previous revision |

All actions require approval. Nothing executes automatically.

---

## Kubernetes Deployment

```bash
# Create namespace and secret
kubectl create namespace ai-sre-system
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=MODEL_API_KEY="***" \
  --from-literal=MODEL_NAME="$MODEL_NAME" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="$WRITE_ALLOWED_NAMESPACES"

# Deploy
kubectl apply -k deploy
```

Image: `ghcr.io/kmjayadeep/k8s-ai-sre:main`

---

## Documentation

- [Quick Start](docs/quickstart.md)
- [Contributing Guide](docs/contributing.md)
- [Developer Guide](docs/developer.md)
- [Deployment Guide](docs/deployment.md)
- [Testing Guide](TESTING.md)
- [Maintainers Guide](docs/maintainers.md)
- [Portkey Integration](docs/portkey.md)

## Contributor Workflow

Contributing changes? Start with [docs/contributing.md](docs/contributing.md).

From there, use:

- `docs/developer.md` for local setup, validation commands, and PR handoff expectations
- `TESTING.md` for end-to-end and kind-based validation
- `docs/maintainers.md` for docs ownership and merge routing

---

## License

MIT
