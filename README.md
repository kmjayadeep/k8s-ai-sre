# k8s-ai-sre

> AI-powered incident response for Kubernetes. Investigate, propose, approve, execute.

Stop spending hours debugging production. `k8s-ai-sre` is an AI co-pilot that investigates cluster incidents, proposes concrete remediation steps, and executes them only after you explicitly approve — with guardrails in place.

---

## Start Here

- Prefer the published docs site? Open [kmjayadeep.github.io/k8s-ai-sre](https://kmjayadeep.github.io/k8s-ai-sre/).
- Want a local trial run? Read the [Quick Start](docs/quickstart.md).
- Deploying to a cluster? Use the [Deployment Guide](docs/deployment.md).
- Validating the full loop? Follow the [Testing Guide](TESTING.md).
- Understanding the internals? Read the [Architecture Guide](docs/architecture.md).

## Why Teams Use It

- Investigates incidents with real cluster evidence instead of guesswork
- Requires explicit approval before any mutating action runs
- Works through both HTTP and Telegram so operators can respond quickly
- Preserves an audit trail for incident, proposal, and approval state

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
# 1. Install dependencies
uv sync

# 2. Configure model access
export MODEL_API_KEY=***
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.groq.com/openai/v1
export MODEL_NAME=openai/gpt-oss-20b
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo

# 3. Start the service
uv run main.py

# 4. Trigger an investigation
curl -X POST http://127.0.0.1:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"my-deploy"}'
```

Or trigger via Alertmanager — see the [Quick Start guide](docs/quickstart.md).

## What You See Next

The API returns a normalized incident payload, including the investigation summary, proposed actions, and notification result:

```json
{
  "incident_id": "a1b2c3d4e5",
  "kind": "deployment",
  "namespace": "ai-sre-demo",
  "name": "bad-deploy",
  "answer": "Summary: image pull failure. The deployment is failing because the referenced image tag cannot be pulled.",
  "evidence": "",
  "source": "manual",
  "action_ids": ["abc12345"],
  "proposed_actions": [
    {
      "action_id": "abc12345",
      "action_type": "rollout-restart",
      "namespace": "ai-sre-demo",
      "name": "bad-deploy",
      "params": {},
      "expires_at": null,
      "approve_command": "/approve abc12345",
      "reject_command": "/reject abc12345"
    }
  ],
  "notification_status": "Telegram notification sent."
}
```

Telegram operators get a concise, action-first incident summary with inline approve/reject commands ready to copy. Model reasoning traces (`<think>` blocks) are automatically stripped before sending:

```text
Incident a1b2c3d4e5
Target: deployment ai-sre-demo/bad-deploy
Cluster: prod-cluster  (shown when K8S_CLUSTER_NAME is set)
Quick summary: image pull failure. The deployment is failing because the referenced image tag cannot be pulled.
Root cause: image pull failure
Action items:
1. Automated option: rollout-restart ai-sre-demo/bad-deploy
   approve: /approve abc12345
   reject: /reject abc12345
```

Use `/status <incident-id>` to confirm the notification state and action IDs.

---

## Operator Workflow

| Step | Operator experience |
|---|---|
| Investigate | Send an HTTP request or receive an Alertmanager webhook |
| Review | Read the incident summary, evidence, and proposed action list |
| Approve | Use Telegram (`/approve <action-id>`) or the HTTP operator endpoint |
| Reject | Discard unsafe or irrelevant actions with `/reject <action-id>` |
| Verify | Check `/status <incident-id>`, the incident inspector UI, or Prometheus metrics |

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/incident <id>` | Get incident details and proposed actions |
| `/status <id>` | Check action execution status |
| `/approve <id>` | Approve an action for execution |
| `/reject <id>` | Reject and discard an action |

---

## Built-In Guardrails

| Guardrail | Why it matters |
|---|---|
| Explicit approval | No action runs automatically |
| Namespace allow-list | Limits where write actions may execute |
| `kubectl auth can-i` checks | Fails closed when the service lacks authority |
| Audit trail | Keeps incident, proposal, and decision state inspectable |
| Deterministic fallback proposals | Still suggests safe actions if the model omits a tool call |

## Supported Actions

| Action | When to Use |
|--------|-------------|
| `delete-pod` | Pod stuck in CrashLoopBackOff or Pending — kubelet will restart |
| `rollout-restart` | Deployment needs a fresh start without changing config |
| `scale` | Replica count too low or too high |
| `rollout-undo` | Bad deployment — roll back to the previous revision |

---

## Kubernetes Deployment

Install via the published Helm repository (no repo clone required):

```bash
helm repo add k8s-ai-sre https://raw.githubusercontent.com/kmjayadeep/k8s-ai-sre/gh-pages/
helm repo update
helm install k8s-ai-sre k8s-ai-sre/k8s-ai-sre \
  --namespace ai-sre-system \
  --create-namespace \
  --version 0.1.0 \
  --values my-values.yaml
```

The chart repository is published from `chart/` by `.github/workflows/helm-chart-release.yml` whenever chart files change on `main`.

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

## Documentation Map

- [Quick Start](docs/quickstart.md)
- [Deployment Guide](docs/deployment.md)
- [Developer Guide](docs/developer.md)
- [Testing Guide](TESTING.md)
- [Architecture Guide](docs/architecture.md)
- [Portkey Integration](docs/portkey.md)

---

## License

MIT
