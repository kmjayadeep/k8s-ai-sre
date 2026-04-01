# Deployment

Kubernetes manifests live in `deploy/` and target this image by default:

```text
ghcr.io/kmjayadeep/k8s-ai-sre:main
```

## Create namespace and secret

```bash
kubectl create namespace ai-sre-system --dry-run=client -o yaml | kubectl apply -f -
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=PORTKEY_API_KEY="$PORTKEY_API_KEY" \
  --from-literal=MODEL_NAME="$MODEL_NAME" \
  --from-literal=MODEL_PROVIDER="$MODEL_PROVIDER" \
  --from-literal=MODEL_BASE_URL="$MODEL_BASE_URL" \
  --from-literal=MODEL_API_KEY="$MODEL_API_KEY" \
  --from-literal=TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
  --from-literal=TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
  --from-literal=TELEGRAM_ALLOWED_CHAT_IDS="$TELEGRAM_ALLOWED_CHAT_IDS" \
  --from-literal=TELEGRAM_POLL_ENABLED="${TELEGRAM_POLL_ENABLED:-true}" \
  --from-literal=TELEGRAM_POLL_TIMEOUT_SECONDS="${TELEGRAM_POLL_TIMEOUT_SECONDS:-30}" \
  --from-literal=TELEGRAM_HTTP_TIMEOUT_SECONDS="${TELEGRAM_HTTP_TIMEOUT_SECONDS:-35}" \
  --from-literal=TELEGRAM_POLL_INTERVAL_SECONDS="${TELEGRAM_POLL_INTERVAL_SECONDS:-1}" \
  --from-literal=TELEGRAM_POLL_BACKOFF_SECONDS="${TELEGRAM_POLL_BACKOFF_SECONDS:-5}" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="$WRITE_ALLOWED_NAMESPACES" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Apply deployment

```bash
kubectl apply -k deploy
kubectl get pods -n ai-sre-system
kubectl get svc -n ai-sre-system
```
