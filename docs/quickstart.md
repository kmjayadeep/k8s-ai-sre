# Quick Start

Deploy `k8s-ai-sre` on Kubernetes using the Helm chart.

**Prerequisites:** Kubernetes cluster, `kubectl`, [Helm](https://helm.sh/docs/intro/install/).

## 1. Configure values

Copy and edit the example values file:

```bash
cp chart/examples/with-inline-secret.yaml my-values.yaml
# Edit my-values.yaml with your credentials
```

Required changes in `my-values.yaml`:
```yaml
secretData:
  PORTKEY_API_KEY: "your-portkey-api-key"
  MODEL_NAME: "openai/gpt-oss-20b"
  MODEL_PROVIDER: "groq"
  MODEL_BASE_URL: "https://api.portkey.ai/v1"
  WRITE_ALLOWED_NAMESPACES: "ai-sre-demo"
```

## 2. Install the chart

```bash
helm install k8s-ai-sre ./chart \
  --namespace ai-sre-system \
  --create-namespace \
  --values my-values.yaml \
  --timeout 2m \
  --wait
```

## 3. Verify

```bash
kubectl -n ai-sre-system get pods,svc
kubectl -n ai-sre-system rollout status deploy/k8s-ai-sre
curl -s $(kubectl -n ai-sre-system get svc k8s-ai-sre -o jsonpath='{.spec.clusterIP}')/healthz
```

## 4. Trigger investigation

```bash
curl -X POST http://localhost:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"bad-deploy"}'
```

## Upgrading

```bash
helm upgrade --install k8s-ai-sre ./chart \
  --namespace ai-sre-system \
  --values my-values.yaml \
  --timeout 2m \
  --wait
```

## Uninstalling

```bash
helm uninstall k8s-ai-sre --namespace ai-sre-system
# Note: does not delete write namespaces or external secrets
```

For production, see [`docs/deployment.md`](deployment.md) for full deployment runbook including rollback procedures.

For local development, see [`docs/developer.md`](developer.md).
