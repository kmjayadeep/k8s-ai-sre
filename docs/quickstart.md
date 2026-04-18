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

Deploy `k8s-ai-sre` on Kubernetes using the Helm chart published from this repository.

**Prerequisites:** Kubernetes cluster, `kubectl`, [Helm](https://helm.sh/docs/intro/install/).

### 1. Add the Helm repository

```bash
helm repo add k8s-ai-sre https://raw.githubusercontent.com/kmjayadeep/k8s-ai-sre/gh-pages/
helm repo update
```

### 2. Create the credentials secret

Create a `Secret` named `k8s-ai-sre-env` in the `ai-sre-system` namespace. Replace the values below with your own.

```bash
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=MODEL_API_KEY="your-api-key" \
  --from-literal=MODEL_NAME="openai/gpt-oss-20b" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="ai-sre-demo" \
  --dry-run=client -o yaml | kubectl apply -f -
```

Required secret keys:

| Key | Required | Default |
|---|---|---|
| `MODEL_API_KEY` | Yes | — |
| `MODEL_NAME` | Yes | — |
| `WRITE_ALLOWED_NAMESPACES` | Yes | — |
| `MODEL_PROVIDER` | No | `groq` |
| `MODEL_BASE_URL` | No | `https://api.groq.com/openai/v1` |
| `TELEGRAM_BOT_TOKEN` | No | — |
| `TELEGRAM_CHAT_ID` | No | — |
| `OPERATOR_API_TOKEN` | No | — |

Add any optional keys with extra `--from-literal=` flags in the same command.

### 3. Install the chart

```bash
helm install k8s-ai-sre k8s-ai-sre/k8s-ai-sre \
  --namespace ai-sre-system \
  --create-namespace \
  --set secretMode=existing \
  --set existingSecret.name=k8s-ai-sre-env \
  --set writeAllowedNamespaces[0]=ai-sre-demo \
  --timeout 2m \
  --wait
```

To add more write-allowed namespaces, append `--set writeAllowedNamespaces[1]=production`.

To enable Telegram notifications, ensure your secret contains `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` before installing, then add `--set secretMode=existing` as shown above.

### 4. Verify

```bash
kubectl -n ai-sre-system get pods,svc
kubectl -n ai-sre-system rollout status deploy/k8s-ai-sre
kubectl -n ai-sre-system get secret k8s-ai-sre-env   # confirm the secret is present
curl -s $(kubectl -n ai-sre-system get svc k8s-ai-sre -o jsonpath='{.spec.clusterIP}')/healthz
```

Expected: `{"status":"ok","config":"ok"}` — confirms the service started and credentials are valid.

### Upgrading

```bash
helm repo update
helm upgrade --install k8s-ai-sre k8s-ai-sre/k8s-ai-sre \
  --namespace ai-sre-system \
  --set secretMode=existing \
  --set existingSecret.name=k8s-ai-sre-env \
  --set writeAllowedNamespaces[0]=ai-sre-demo \
  --timeout 2m \
  --wait
```

### Uninstalling

```bash
helm uninstall k8s-ai-sre --namespace ai-sre-system
# Does not delete the credentials secret or write namespaces.
```

### Alternatives

#### Inline secrets (credentials in values file)

If you prefer to keep credentials in a local file instead of a pre-created Secret, use `secretMode=inline` with a values file:

```bash
helm install k8s-ai-sre k8s-ai-sre/k8s-ai-sre \
  --namespace ai-sre-system \
  --create-namespace \
  --values my-values.yaml
```

Example `my-values.yaml`:

```yaml
secretMode: inline
secretData:
  MODEL_API_KEY: "your-api-key"
  MODEL_NAME: "openai/gpt-oss-20b"
  WRITE_ALLOWED_NAMESPACES: "ai-sre-demo"
  MODEL_PROVIDER: "groq"
  MODEL_BASE_URL: "https://api.groq.com/openai/v1"
```

See `chart/examples/with-inline-secret.yaml` for the full example including Telegram and operator token options.

#### External Secret (credentials managed outside the chart)

If your cluster uses an external secrets manager (Vault, ESO, Sealed Secrets, etc.), create the Secret yourself and reference it by name:

```bash
helm install k8s-ai-sre k8s-ai-sre/k8s-ai-sre \
  --namespace ai-sre-system \
  --create-namespace \
  --set secretMode=existing \
  --set existingSecret.name=your-secret-name \
  --set writeAllowedNamespaces[0]=ai-sre-demo \
  --timeout 2m \
  --wait
```

See `chart/examples/with-existing-secret.yaml` for reference.

For production, see [`docs/deployment.md`](deployment.md) for full deployment runbook including rollback procedures.

For local development, see [`docs/developer.md`](developer.md).

## Telegram Approval Experience

The `/incident <incident-id>` command returns a concise, action-first operator summary:

```text
Incident a1b2c3d4e5
Target: deployment ai-sre-demo/bad-deploy
Cluster: prod-cluster  (shown when K8S_CLUSTER_NAME is set)
Quick summary: image pull failure
Root cause: image pull failure
Action items:
1. Automated option: rollout-restart ai-sre-demo/bad-deploy
   approve: /approve abc12345
   reject: /reject abc12345
```

Use `/status <incident-id>` to confirm the notification state and action IDs, then `/approve <action-id>` or `/reject <action-id>` to decide the proposal.

**Note:** Set `K8S_CLUSTER_NAME` (or `CLUSTER_NAME`, `KUBE_CLUSTER_NAME`, `KUBERNETES_CLUSTER_NAME`) to include the cluster name in Telegram output. Model `<think>` reasoning blocks are automatically stripped before sending.
