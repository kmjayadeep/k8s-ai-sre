# Deployment Runbook (Canonical)

Use this as the canonical deploy + rollback runbook for Kubernetes.

## Runtime startup contract

Secret name expected by the manifest: `k8s-ai-sre-env` in namespace `ai-sre-system`.

| Variable | Required | Runtime behavior |
| --- | --- | --- |
| `MODEL_API_KEY` or `PORTKEY_API_KEY` | Yes | Process fails at startup when neither key is set. |
| `MODEL_NAME` | Yes | Process fails at startup when empty. |
| `MODEL_PROVIDER` | No | Defaults to `groq`. |
| `MODEL_BASE_URL` | No | Defaults to Portkey gateway URL in code. |
| `TELEGRAM_BOT_TOKEN` | No | Must be paired with `TELEGRAM_CHAT_ID` when set. |
| `TELEGRAM_CHAT_ID` | No | Must be paired with `TELEGRAM_BOT_TOKEN` when set. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Recommended when polling enabled | If set, `TELEGRAM_BOT_TOKEN` must be set. |
| `TELEGRAM_POLL_ENABLED` | No | Defaults to enabled (`true`-like values start polling). |
| `TELEGRAM_POLL_TIMEOUT_SECONDS` | No | Invalid/non-positive values fall back to defaults. |
| `TELEGRAM_HTTP_TIMEOUT_SECONDS` | No | Invalid/non-positive values fall back; clamped to safe value relative to poll timeout. |
| `TELEGRAM_POLL_INTERVAL_SECONDS` | No | Poll loop sleep interval between successful cycles. |
| `TELEGRAM_POLL_BACKOFF_SECONDS` | No | Backoff after poll failure. |
| `OPERATOR_API_TOKEN` | Required for HTTP approve/reject endpoints | `/actions/{id}/approve|reject` returns `503` when not set. |
| `WRITE_ALLOWED_NAMESPACES` | Strongly recommended | Empty means writes are allowed in all namespaces. |

Important current behavior:

- startup performs fail-fast runtime config validation before serving traffic.
- `/healthz` still reports `ok` only after startup preflight passes.

## Preflight checklist

Run these checks before rollout:

```bash
kubectl config current-context
kubectl get ns ai-sre-system
kubectl -n ai-sre-system get sa k8s-ai-sre
kubectl -n ai-sre-system get secret k8s-ai-sre-env -o yaml
```

Confirm the secret includes at least:

- one of `MODEL_API_KEY` or `PORTKEY_API_KEY`
- `WRITE_ALLOWED_NAMESPACES` (non-empty in production-like environments)
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` if chat notifications are expected
- `OPERATOR_API_TOKEN` if HTTP approval endpoints are used for automation

## Deploy

Kubernetes manifests live in `deploy/` and default image is:

```text
ghcr.io/kmjayadeep/k8s-ai-sre:main
```

Create namespace and secret (idempotent):

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
  --from-literal=OPERATOR_API_TOKEN="$OPERATOR_API_TOKEN" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="$WRITE_ALLOWED_NAMESPACES" \
  --dry-run=client -o yaml | kubectl apply -f -
```

Apply manifests and wait for readiness:

```bash
kubectl apply -k deploy
kubectl -n ai-sre-system rollout status deployment/k8s-ai-sre
kubectl -n ai-sre-system get pods,svc
```

## Post-deploy validation

```bash
kubectl -n ai-sre-system port-forward svc/k8s-ai-sre 18080:80
curl -fsS http://127.0.0.1:18080/healthz
```

If model credentials are present, run a smoke investigation:

```bash
curl -X POST http://127.0.0.1:18080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"bad-deploy"}'
```

## Rollback

Preferred rollback (explicit known-good image):

```bash
kubectl -n ai-sre-system set image deployment/k8s-ai-sre app=ghcr.io/kmjayadeep/k8s-ai-sre:<known-good-tag-or-digest>
kubectl -n ai-sre-system rollout status deployment/k8s-ai-sre
```

Emergency rollback (previous ReplicaSet):

```bash
kubectl -n ai-sre-system rollout undo deployment/k8s-ai-sre
kubectl -n ai-sre-system rollout status deployment/k8s-ai-sre
```

After rollback, repeat `/healthz` and one investigation smoke check.

## Incident response: Telegram/API degradation

### Telegram degradation

Symptoms:

- investigation responses include `notification_status` failures
- logs show repeated `telegram_poll_loop_failed`
- commands are ignored from unexpected chats when allow-list is configured

Response:

1. check bot token/chat id/allowed chat ids in `k8s-ai-sre-env`
2. check for competing bot consumers (`HTTP Error 409: Conflict` in logs)
3. if chat path is degraded, continue operator approvals through HTTP token path
4. after fix, verify with `/status <incident-id>` and `/approve <action-id>` from an allowed chat

### API degradation

Symptoms:

- `/healthz` not reachable through service/port-forward
- `/investigate` or webhook endpoints failing
- HTTP approve/reject returns `503` (`OPERATOR_API_TOKEN` missing)

Response:

1. inspect workload and events:
   - `kubectl -n ai-sre-system get pods`
   - `kubectl -n ai-sre-system describe pod <pod-name>`
   - `kubectl -n ai-sre-system logs deploy/k8s-ai-sre --tail=200`
2. confirm secret keys still present and non-empty (`k8s-ai-sre-env`)
3. if regression is tied to new image/config, execute rollback steps above
4. re-run `/healthz` and investigation smoke test before restoring traffic
