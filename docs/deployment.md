# Deployment Runbook (Canonical)

<div class="page-intro">
  <p>Use this page when you are moving from a local proof-of-concept to a cluster install. It keeps the startup contract, preflight checks, deployment steps, and rollback path on one page so operators do not have to assemble them from scattered repo docs.</p>
</div>

Use this as the canonical deploy + rollback runbook for Kubernetes.

**Recommended:** Use the published Helm repository for production installs. The Helm chart handles namespace, RBAC, ServiceAccount, and Secret creation automatically.

```bash
helm repo add k8s-ai-sre https://raw.githubusercontent.com/kmjayadeep/k8s-ai-sre/gh-pages/
helm repo update
kubectl create namespace ai-sre-system
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=MODEL_API_KEY="$MODEL_API_KEY" \
  --from-literal=MODEL_NAME="$MODEL_NAME" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="$WRITE_ALLOWED_NAMESPACES"
helm install k8s-ai-sre k8s-ai-sre/k8s-ai-sre \
  --namespace ai-sre-system \
  --create-namespace \
  --set secretMode=existing \
  --set existingSecret.name=k8s-ai-sre-env \
  --set writeAllowedNamespaces[0]=ai-sre-demo \
  --timeout 2m \
  --wait
```

See [docs/quickstart.md](quickstart.md) for the full Helm install guide, or `chart/examples/` for inline and existing-secret modes.

**Alternative:** Use `kubectl apply -k deploy` (see below).

<div class="trust-panel">
  <p><strong>Human-facing default:</strong> start with the Helm path unless you have a specific reason to work directly with the raw manifests. The Helm chart is the shorter and more repeatable operator path.</p>
</div>

## Runtime startup contract

Secret name expected by the manifest: `k8s-ai-sre-env` in namespace `ai-sre-system`.

| Variable | Required | Runtime behavior |
| --- | --- | --- |
| `MODEL_API_KEY` | Yes | Process fails at startup when not set. |
| `MODEL_NAME` | Yes | Process fails at startup when empty. |
| `MODEL_PROVIDER` | No | Defaults to `groq`. |
| `MODEL_BASE_URL` | No | Defaults to `https://api.groq.com/openai/v1`. |
| `TELEGRAM_BOT_TOKEN` | No | Must be paired with `TELEGRAM_CHAT_ID` when set. |
| `TELEGRAM_CHAT_ID` | No | Must be paired with `TELEGRAM_BOT_TOKEN` when set. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Recommended when polling enabled | If set, `TELEGRAM_BOT_TOKEN` must be set. |
| `TELEGRAM_POLL_ENABLED` | No | Defaults to enabled (`true`-like values start polling). |
| `TELEGRAM_POLL_TIMEOUT_SECONDS` | No | Invalid/non-positive values fall back to defaults. |
| `TELEGRAM_HTTP_TIMEOUT_SECONDS` | No | Invalid/non-positive values fall back; clamped to safe value relative to poll timeout. |
| `TELEGRAM_POLL_INTERVAL_SECONDS` | No | Poll loop sleep interval between successful cycles. |
| `TELEGRAM_POLL_BACKOFF_SECONDS` | No | Backoff after poll failure. |
| `OPERATOR_API_TOKEN` | Required for HTTP approve/reject endpoints | `/actions/{id}/approve|reject` returns `503` when not set. |
| `WRITE_ALLOWED_NAMESPACES` | Yes | Process startup fails when empty or unset; mutating actions are allowed only inside this allow-list. |
| `K8S_CLUSTER_NAME` | No | Sets cluster name in Telegram output (also: `CLUSTER_NAME`, `KUBE_CLUSTER_NAME`, `KUBERNETES_CLUSTER_NAME`). |

Important current behavior:

- startup performs fail-fast runtime config validation before serving traffic.
- `/healthz` still reports `ok` only after startup preflight passes.
- startup fails fast when `WRITE_ALLOWED_NAMESPACES` is missing or resolves to an empty list.

## Preflight checklist

Run these checks before rollout:

```bash
kubectl config current-context
kubectl get ns ai-sre-system
kubectl -n ai-sre-system get sa k8s-ai-sre
kubectl -n ai-sre-system get secret k8s-ai-sre-env -o yaml
```

Confirm the secret includes at least:

- `MODEL_API_KEY`
- `WRITE_ALLOWED_NAMESPACES` (required, non-empty)
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

## Incident response: Alertmanager ingestion

The service tracks Alertmanager delivery outcomes and exposes visibility and recovery endpoints.

### Ingestion status

`GET /ingestion-status` returns the current Alertmanager ingestion health snapshot:

```json
{
  "status": "healthy",
  "window_size": 300,
  "failed_deliveries": 0,
  "failure_rate": 0.0,
  "degrade_threshold": 0.2,
  "min_samples": 5,
  "failed_by_receiver": {},
  "failed_by_target": {},
  "last_failure_at": null,
  "last_failure_detail": null
}
```

Threshold and sample size are controlled by environment variables:

- `ALERTMANAGER_INGESTION_FAILURE_THRESHOLD` (default `0.2`): failure rate above which `status` becomes `"degraded"`
- `ALERTMANAGER_INGESTION_MIN_SAMPLES` (default `5`): minimum samples required before declaring degradation

### Reconciliation

`POST /reconcile/alertmanager` re-processes an Alertmanager firing payload to recover incidents that may have been missed during a degraded ingestion window:

```bash
curl -X POST http://127.0.0.1:8080/reconcile/alertmanager \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <ALERTMANAGER_API_KEY>' \
  -d @examples/alertmanager-bad-deploy.json
```

Idempotent: re-running the same payload is safe and skips already-resolved incidents.

Response:

```json
{
  "receiver": "kubernetes-alerting",
  "active_alerts_seen": 1,
  "recovered_incidents": 1,
  "skipped_existing_incidents": 0,
  "failed_alerts": 0,
  "recovered_incident_ids": ["a1b2c3d4e5"]
}
```

When to use: after resolving an Alertmanager delivery outage, run `/reconcile/alertmanager` with the missed alerts to ensure the service processes the firing events and recreates open incidents.

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
