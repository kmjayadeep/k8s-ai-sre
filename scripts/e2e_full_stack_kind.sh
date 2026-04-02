#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-k8s-ai-sre}"
APP_NS="${APP_NAMESPACE:-ai-sre-system}"
DEMO_NS="${DEMO_NAMESPACE:-ai-sre-demo}"
MON_NS="${MONITORING_NAMESPACE:-monitoring}"
RELEASE_NAME="${MONITORING_RELEASE_NAME:-kube-prom-stack}"
APP_IMAGE="${APP_IMAGE:-k8s-ai-sre:e2e}"
APP_PORT_FORWARD="${APP_PORT_FORWARD:-18080:80}"
AM_PORT_FORWARD="${ALERTMANAGER_PORT_FORWARD:-19093:9093}"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-900}"
OPERATOR_ID="${OPERATOR_ID:-e2e-kind-runner}"

PROM_STACK_VALUES="${ROOT_DIR}/examples/monitoring/kube-prom-stack-values.yaml"
PROM_RULE="${ROOT_DIR}/examples/monitoring/bad-deploy-prometheus-rule.yaml"
SCENARIO_MANIFEST="${ROOT_DIR}/examples/kind-bad-deploy.yaml"
SECRET_NAME="k8s-ai-sre-env"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

discover_alertmanager_service() {
  kubectl -n "$MON_NS" get svc -l "release=${RELEASE_NAME}" -o name 2>/dev/null \
    | sed 's#service/##' \
    | rg 'alertmanager' \
    | head -n 1 || true
}

discover_alertmanager_name() {
  kubectl -n "$MON_NS" get alertmanager \
    -l "app.kubernetes.io/instance=${RELEASE_NAME}" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}

resolve_helm_bin() {
  if command -v helm >/dev/null 2>&1; then
    HELM_BIN="$(command -v helm)"
    return 0
  fi

  local arch
  arch="$(uname -m)"
  case "$arch" in
    x86_64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *)
      echo "Unsupported architecture for automatic helm download: $arch"
      return 1
      ;;
  esac

  local os
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  local tmp_dir
  tmp_dir="$(mktemp -d /tmp/k8s-ai-sre-helm-XXXXXX)"
  local helm_tgz="${tmp_dir}/helm.tgz"
  local helm_url="https://get.helm.sh/helm-v3.16.4-${os}-${arch}.tar.gz"

  echo "helm not found; downloading ${helm_url}..."
  curl -fsSL "$helm_url" -o "$helm_tgz"
  tar -xzf "$helm_tgz" -C "$tmp_dir"
  HELM_BIN="${tmp_dir}/${os}-${arch}/helm"
  if [[ ! -x "$HELM_BIN" ]]; then
    echo "Failed to prepare helm binary at ${HELM_BIN}"
    return 1
  fi
}

secret_value_or_empty() {
  local namespace="$1"
  local secret_name="$2"
  local key="$3"
  local encoded
  encoded="$(kubectl -n "$namespace" get secret "$secret_name" -o "jsonpath={.data.${key}}" 2>/dev/null || true)"
  if [[ -z "$encoded" ]]; then
    echo ""
    return 0
  fi
  echo "$encoded" | base64 --decode 2>/dev/null || echo ""
}

wait_for_json_field() {
  local url="$1"
  local jq_expr="$2"
  local timeout="$3"
  local start_ts
  start_ts="$(date +%s)"

  while true; do
    if curl -fsS "$url" | jq -e "$jq_expr" >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - start_ts > timeout )); then
      return 1
    fi
    sleep 5
  done
}

collect_evidence() {
  local output_dir="$1"
  mkdir -p "$output_dir"
  curl -fsS "${APP_LOCAL_URL}/incidents" > "${output_dir}/incidents.json" || true
  curl -fsS "${AM_LOCAL_URL}/api/v2/alerts" > "${output_dir}/alertmanager-alerts.json" || true
  kubectl -n "$DEMO_NS" get deployment bad-deploy -o yaml > "${output_dir}/bad-deploy-state.yaml" || true
  kubectl -n "$DEMO_NS" get pods -l app=bad-deploy -o wide > "${output_dir}/bad-deploy-pods.txt" || true
}

cleanup() {
  if [[ -n "${APP_PF_PID:-}" ]] && kill -0 "$APP_PF_PID" >/dev/null 2>&1; then
    kill "$APP_PF_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${AM_PF_PID:-}" ]] && kill -0 "$AM_PF_PID" >/dev/null 2>&1; then
    kill "$AM_PF_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

for bin in kubectl kind docker jq curl; do
  require_cmd "$bin"
done
resolve_helm_bin

HAS_EXISTING_SECRET=false
if kubectl -n "$APP_NS" get secret "$SECRET_NAME" >/dev/null 2>&1; then
  HAS_EXISTING_SECRET=true
  echo "Found existing ${APP_NS}/${SECRET_NAME}; using it to backfill missing env vars."
  PORTKEY_API_KEY="${PORTKEY_API_KEY:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "PORTKEY_API_KEY")}"
  MODEL_API_KEY="${MODEL_API_KEY:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "MODEL_API_KEY")}"
  MODEL_NAME="${MODEL_NAME:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "MODEL_NAME")}"
  MODEL_PROVIDER="${MODEL_PROVIDER:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "MODEL_PROVIDER")}"
  MODEL_BASE_URL="${MODEL_BASE_URL:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "MODEL_BASE_URL")}"
  TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "TELEGRAM_BOT_TOKEN")}"
  TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "TELEGRAM_CHAT_ID")}"
  TELEGRAM_ALLOWED_CHAT_IDS="${TELEGRAM_ALLOWED_CHAT_IDS:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "TELEGRAM_ALLOWED_CHAT_IDS")}"
  OPERATOR_API_TOKEN="${OPERATOR_API_TOKEN:-$(secret_value_or_empty "$APP_NS" "$SECRET_NAME" "OPERATOR_API_TOKEN")}"
fi

if [[ -z "${MODEL_API_KEY:-}" && -z "${PORTKEY_API_KEY:-}" ]]; then
  echo "Set MODEL_API_KEY or PORTKEY_API_KEY, or pre-create ${APP_NS}/${SECRET_NAME} with those keys."
  exit 1
fi

if [[ -z "${OPERATOR_API_TOKEN:-}" ]]; then
  echo "Set OPERATOR_API_TOKEN, or pre-create ${APP_NS}/${SECRET_NAME} with OPERATOR_API_TOKEN."
  exit 1
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" || -z "${TELEGRAM_ALLOWED_CHAT_IDS:-}" ]]; then
  echo "Set Telegram env vars, or pre-create ${APP_NS}/${SECRET_NAME} with TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID/TELEGRAM_ALLOWED_CHAT_IDS."
  exit 1
fi

echo "Building and loading app image into kind cluster ${CLUSTER_NAME}..."
docker build -t "$APP_IMAGE" "$ROOT_DIR"
kind load docker-image "$APP_IMAGE" --name "$CLUSTER_NAME"

echo "Applying app prerequisites and runtime secret..."
kubectl create namespace "$APP_NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$APP_NS" create secret generic "$SECRET_NAME" \
  --from-literal=PORTKEY_API_KEY="${PORTKEY_API_KEY:-}" \
  --from-literal=MODEL_NAME="${MODEL_NAME:-openai/gpt-oss-20b}" \
  --from-literal=MODEL_PROVIDER="${MODEL_PROVIDER:-groq}" \
  --from-literal=MODEL_BASE_URL="${MODEL_BASE_URL:-https://api.portkey.ai/v1}" \
  --from-literal=MODEL_API_KEY="${MODEL_API_KEY:-}" \
  --from-literal=TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}" \
  --from-literal=TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}" \
  --from-literal=TELEGRAM_ALLOWED_CHAT_IDS="${TELEGRAM_ALLOWED_CHAT_IDS}" \
  --from-literal=TELEGRAM_POLL_ENABLED="${TELEGRAM_POLL_ENABLED:-true}" \
  --from-literal=TELEGRAM_POLL_TIMEOUT_SECONDS="${TELEGRAM_POLL_TIMEOUT_SECONDS:-30}" \
  --from-literal=TELEGRAM_HTTP_TIMEOUT_SECONDS="${TELEGRAM_HTTP_TIMEOUT_SECONDS:-35}" \
  --from-literal=TELEGRAM_POLL_INTERVAL_SECONDS="${TELEGRAM_POLL_INTERVAL_SECONDS:-1}" \
  --from-literal=TELEGRAM_POLL_BACKOFF_SECONDS="${TELEGRAM_POLL_BACKOFF_SECONDS:-5}" \
  --from-literal=OPERATOR_API_TOKEN="${OPERATOR_API_TOKEN}" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="${WRITE_ALLOWED_NAMESPACES:-${DEMO_NS}}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Deploying app manifests and forcing local image usage..."
kubectl apply -k "${ROOT_DIR}/deploy"
kubectl -n "$APP_NS" set image deployment/k8s-ai-sre app="$APP_IMAGE"
# Ensure the deployed runtime token matches the token used by this script.
kubectl -n "$APP_NS" set env deployment/k8s-ai-sre OPERATOR_API_TOKEN="${OPERATOR_API_TOKEN}" >/dev/null
kubectl -n "$APP_NS" patch deployment k8s-ai-sre --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]'
# Force a new ReplicaSet even when reusing the same local tag.
kubectl -n "$APP_NS" patch deployment k8s-ai-sre --type='merge' \
  -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"k8s-ai-sre/e2e-run-ts\":\"$(date +%s)\"}}}}}"
kubectl -n "$APP_NS" rollout status deployment/k8s-ai-sre --timeout=5m

echo "Installing kube-prometheus-stack with Alertmanager webhook receiver..."
"$HELM_BIN" repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
"$HELM_BIN" repo update >/dev/null
kubectl create namespace "$MON_NS" --dry-run=client -o yaml | kubectl apply -f -
"$HELM_BIN" upgrade --install "$RELEASE_NAME" prometheus-community/kube-prometheus-stack \
  --namespace "$MON_NS" \
  --wait \
  --timeout 10m \
  -f "$PROM_STACK_VALUES"

kubectl apply -f "$PROM_RULE"

echo "Preparing failed workload target..."
kubectl create namespace "$DEMO_NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$SCENARIO_MANIFEST"

ALERTMANAGER_NAME="$(discover_alertmanager_name)"
if [[ -n "$ALERTMANAGER_NAME" ]]; then
  kubectl -n "$MON_NS" wait --for=condition=Reconciled "alertmanager/${ALERTMANAGER_NAME}" --timeout=5m
fi

ALERTMANAGER_SERVICE_NAME="${ALERTMANAGER_SERVICE_NAME:-$(discover_alertmanager_service)}"
if [[ -z "$ALERTMANAGER_SERVICE_NAME" ]]; then
  echo "Failed to discover Alertmanager service for release ${RELEASE_NAME} in namespace ${MON_NS}."
  exit 1
fi

APP_LOCAL_URL="http://127.0.0.1:${APP_PORT_FORWARD%%:*}"
AM_LOCAL_URL="http://127.0.0.1:${AM_PORT_FORWARD%%:*}"

echo "Starting temporary port-forwards..."
kubectl -n "$APP_NS" port-forward svc/k8s-ai-sre "$APP_PORT_FORWARD" >/tmp/k8s-ai-sre-aie30-app-port-forward.log 2>&1 &
APP_PF_PID=$!
kubectl -n "$MON_NS" port-forward "svc/${ALERTMANAGER_SERVICE_NAME}" "$AM_PORT_FORWARD" >/tmp/k8s-ai-sre-aie30-am-port-forward.log 2>&1 &
AM_PF_PID=$!

sleep 5

echo "Waiting for alert to fire in Alertmanager..."
if ! wait_for_json_field "${AM_LOCAL_URL}/api/v2/alerts" '.[] | select(.labels.alertname == "DeploymentReplicasUnavailable" and .labels.namespace == "ai-sre-demo" and .labels.deployment == "bad-deploy")' "$WAIT_TIMEOUT_SECONDS"; then
  echo "Timed out waiting for DeploymentReplicasUnavailable in Alertmanager."
  echo "Alertmanager port-forward log: /tmp/k8s-ai-sre-aie30-am-port-forward.log"
  exit 1
fi

echo "Waiting for alertmanager-sourced incident in service..."
if ! wait_for_json_field "${APP_LOCAL_URL}/incidents" '.incidents[] | select(.source == "alertmanager" and .namespace == "ai-sre-demo" and .name == "bad-deploy")' "$WAIT_TIMEOUT_SECONDS"; then
  echo "Timed out waiting for alertmanager incident in /incidents."
  echo "App port-forward log: /tmp/k8s-ai-sre-aie30-app-port-forward.log"
  exit 1
fi

INCIDENT_JSON="$(curl -fsS "${APP_LOCAL_URL}/incidents" | jq -c 'first(.incidents[] | select(.source == "alertmanager" and .namespace == "ai-sre-demo" and .name == "bad-deploy"))')"
INCIDENT_ID="$(echo "$INCIDENT_JSON" | jq -r '.incident_id')"
ACTION_ID="$(echo "$INCIDENT_JSON" | jq -r '.action_ids[0] // empty')"
EVIDENCE_DIR="/tmp/k8s-ai-sre-aie30"
mkdir -p "$EVIDENCE_DIR"
rm -f "${EVIDENCE_DIR}/failure-reason.txt"
collect_evidence "$EVIDENCE_DIR"
echo "$INCIDENT_JSON" | jq > "${EVIDENCE_DIR}/selected-incident.json"

echo "Incident detected: ${INCIDENT_ID}"
if [[ -z "$ACTION_ID" ]]; then
  echo "No action proposal available; cannot validate approve/execute loop in this run."
  echo "$INCIDENT_JSON" | jq
  echo "No action_ids were produced for incident ${INCIDENT_ID}." > "${EVIDENCE_DIR}/failure-reason.txt"
  echo "Evidence bundle: ${EVIDENCE_DIR}"
  exit 1
fi

echo "Approving action ${ACTION_ID} via operator API token..."
curl -fsS -X POST "${APP_LOCAL_URL}/actions/${ACTION_ID}/approve" \
  -H "Authorization: Bearer ${OPERATOR_API_TOKEN}" \
  -H "X-Operator-Id: ${OPERATOR_ID}" \
  -H 'Content-Type: application/json' > "${EVIDENCE_DIR}/approval.json"

APPROVAL_STATUS="$(jq -r '.status // "unknown"' "${EVIDENCE_DIR}/approval.json")"
if [[ "$APPROVAL_STATUS" != "approved" && "$APPROVAL_STATUS" != "failed" ]]; then
  echo "Unexpected action terminal status after approve call: ${APPROVAL_STATUS}"
  cat "${EVIDENCE_DIR}/approval.json"
  exit 1
fi

echo "Validating remediation effect (best-effort workload health check)..."
if kubectl -n "$DEMO_NS" rollout status deployment/bad-deploy --timeout=3m; then
  REMEDIATION_OUTCOME="deployment_healthy"
else
  REMEDIATION_OUTCOME="deployment_still_unhealthy"
  echo "Deployment did not become healthy after approval (expected for invalid-image scenarios)."
fi

echo "Collecting evidence artifacts..."
collect_evidence "$EVIDENCE_DIR"
printf '{"approval_status":"%s","remediation_outcome":"%s"}\n' "$APPROVAL_STATUS" "$REMEDIATION_OUTCOME" > "${EVIDENCE_DIR}/execution-summary.json"

echo

echo "AIE-30 full pipeline validation succeeded."
echo "Evidence bundle: ${EVIDENCE_DIR}"
echo "Incident: ${INCIDENT_ID}"
echo "Approved action: ${ACTION_ID}"
echo "Approval status: ${APPROVAL_STATUS}"
echo "Remediation outcome: ${REMEDIATION_OUTCOME}"
