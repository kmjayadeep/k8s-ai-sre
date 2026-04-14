# Quick Start

## Local Development

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure model access

Required:

```bash
export MODEL_NAME=openai/gpt-oss-20b
export MODEL_API_KEY=your-api-key
export MODEL_PROVIDER=groq                    # or openai, anthropic, etc.
export MODEL_BASE_URL=https://api.groq.com/openai/v1
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo
```

### Using a different provider

Configure `MODEL_PROVIDER` and `MODEL_BASE_URL` to use any OpenAI-compatible API:

```bash
# Groq (default)
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.groq.com/openai/v1

# OpenAI
export MODEL_PROVIDER=openai
export MODEL_BASE_URL=https://api.openai.com/v1

# Anthropic
export MODEL_PROVIDER=anthropic
export MODEL_BASE_URL=https://api.anthropic.com/v1

# Custom/gateway (e.g., Portkey, local LLM, etc.)
export MODEL_PROVIDER=custom
export MODEL_BASE_URL=https://your-gateway.com/v1
```

See [`docs/portkey.md`](portkey.md) for Portkey-specific configuration.

### 3. Create demo scenario

```bash
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f examples/kind-bad-deploy.yaml
```

### 4. Start the service

```bash
uv run main.py
```

### 5. Trigger investigation

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

Expected API response shape:

```json
{
  "incident_id": "a1b2c3d4e5",
  "kind": "deployment",
  "namespace": "ai-sre-demo",
  "name": "bad-deploy",
  "answer": "Summary: image pull failure",
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

## Kubernetes Deployment

Deploy `k8s-ai-sre` on Kubernetes using the Helm chart.

**Prerequisites:** Kubernetes cluster, `kubectl`, [Helm](https://helm.sh/docs/intro/install/).

### 1. Configure values

Copy and edit the example values file:

```bash
cp chart/examples/with-inline-secret.yaml my-values.yaml
# Edit my-values.yaml with your credentials
```

Required changes in `my-values.yaml`:

```yaml
secretData:
  MODEL_API_KEY: "your-api-key"
  MODEL_NAME: "openai/gpt-oss-20b"
  MODEL_PROVIDER: "groq"
  MODEL_BASE_URL: "https://api.groq.com/openai/v1"
  WRITE_ALLOWED_NAMESPACES: "ai-sre-demo"
```

### 2. Install the chart

```bash
helm install k8s-ai-sre ./chart \
  --namespace ai-sre-system \
  --create-namespace \
  --values my-values.yaml \
  --timeout 2m \
  --wait
```

### 3. Verify

```bash
kubectl -n ai-sre-system get pods,svc
kubectl -n ai-sre-system rollout status deploy/k8s-ai-sre
curl -s $(kubectl -n ai-sre-system get svc k8s-ai-sre -o jsonpath='{.spec.clusterIP}')/healthz
```

### Upgrading

```bash
helm upgrade --install k8s-ai-sre ./chart \
  --namespace ai-sre-system \
  --values my-values.yaml \
  --timeout 2m \
  --wait
```

### Uninstalling

```bash
helm uninstall k8s-ai-sre --namespace ai-sre-system
# Note: does not delete write namespaces or external secrets
```

For production, see [`docs/deployment.md`](deployment.md) for full deployment runbook including rollback procedures.

For local development, see [`docs/developer.md`](developer.md).

## Telegram Approval Experience

The `/incident <incident-id>` command returns a compact operator-facing summary:

```text
Incident a1b2c3d4e5
Target: deployment ai-sre-demo/bad-deploy
Answer:
Summary: image pull failure
Actions:
- abc12345: rollout-restart ai-sre-demo/bad-deploy
```

Use `/status <incident-id>` to confirm the notification state and action IDs, then `/approve <action-id>` or `/reject <action-id>` to decide the proposal.
