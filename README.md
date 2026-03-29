# k8s-ai-sre
AI SRE for monitoring kubernetes and taking action

## Kubernetes Deployment

The Kubernetes manifest is in [deploy/k8s-ai-sre.yaml](deploy/k8s-ai-sre.yaml).

The deployment uses this image:

```text
ghcr.io/kmjayadeep/k8s-ai-sre:main
```

### Secret Configuration

#### Create Or Update The Secret Imperatively

If you already have the values in your shell from `direnv` / `.envrc`, create the secret like this:

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

Then apply the rest of the manifest:

```bash
kubectl apply -f deploy/k8s-ai-sre.yaml
```

### Deploy

```bash
kubectl apply -f deploy/k8s-ai-sre.yaml
kubectl get pods -n ai-sre-system
kubectl get svc -n ai-sre-system
```
