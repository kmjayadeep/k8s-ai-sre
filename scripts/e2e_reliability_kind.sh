#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIO_MANIFEST="${ROOT_DIR}/examples/kind-bad-deploy.yaml"
ALERT_PAYLOAD="${ROOT_DIR}/examples/alertmanager-bad-deploy.json"

RUNS="${RUNS:-5}"
SERVICE_URL="${SERVICE_URL:-http://127.0.0.1:18080}"
EVIDENCE_ROOT="${EVIDENCE_ROOT:-/tmp/k8s-ai-sre-reliability}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="${EVIDENCE_ROOT}/${TIMESTAMP}"
REQUIRE_ACTION_ID="${REQUIRE_ACTION_ID:-1}"
RUN_RESTART_CHECK="${RUN_RESTART_CHECK:-1}"
AUTO_PORT_FORWARD="${AUTO_PORT_FORWARD:-1}"
SYSTEM_NAMESPACE="${SYSTEM_NAMESPACE:-ai-sre-system}"
SYSTEM_SERVICE_NAME="${SYSTEM_SERVICE_NAME:-k8s-ai-sre}"
SYSTEM_DEPLOYMENT_NAME="${SYSTEM_DEPLOYMENT_NAME:-k8s-ai-sre}"

if ! command -v jq >/dev/null 2>&1; then
  echo "Missing dependency: jq"
  exit 1
fi

if [[ -z "${OPERATOR_API_TOKEN:-}" ]]; then
  echo "Missing OPERATOR_API_TOKEN. Set it to use /actions/{id}/approve automation."
  exit 1
fi

if ! [[ "${RUNS}" =~ ^[0-9]+$ ]] || [[ "${RUNS}" -lt 1 ]]; then
  echo "RUNS must be a positive integer."
  exit 1
fi

PF_PID=""
cleanup() {
  if [[ -n "${PF_PID}" ]] && kill -0 "${PF_PID}" >/dev/null 2>&1; then
    kill "${PF_PID}" >/dev/null 2>&1 || true
    wait "${PF_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

start_port_forward() {
  cleanup
  kubectl -n "${SYSTEM_NAMESPACE}" port-forward "svc/${SYSTEM_SERVICE_NAME}" 18080:80 \
    >"${EVIDENCE_DIR}/port-forward.log" 2>&1 &
  PF_PID="$!"
}

wait_for_service() {
  local attempts=30
  local i=0
  while [[ "${i}" -lt "${attempts}" ]]; do
    if curl -fsS "${SERVICE_URL}/healthz" >/dev/null 2>&1; then
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  return 1
}

ensure_service_ready() {
  if curl -fsS "${SERVICE_URL}/healthz" >/dev/null 2>&1; then
    return 0
  fi
  if [[ "${AUTO_PORT_FORWARD}" != "1" ]]; then
    return 1
  fi
  echo "Service not reachable at ${SERVICE_URL}; (re)starting port-forward from ${SYSTEM_NAMESPACE}/${SYSTEM_SERVICE_NAME}..."
  start_port_forward
  wait_for_service
}

curl_with_retry() {
  local method="$1"
  local url="$2"
  local output_file="$3"
  shift 3

  local max_attempts=6
  local attempt=1
  while [[ "${attempt}" -le "${max_attempts}" ]]; do
    ensure_service_ready || true
    if curl -fsS -X "${method}" "$url" "$@" >"${output_file}"; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 2
  done
  return 1
}

snapshot_cluster_state() {
  local output_path="$1"
  {
    echo "# generated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "## deployment"
    kubectl -n ai-sre-demo get deployment bad-deploy -o wide || true
    echo
    echo "## pods"
    kubectl -n ai-sre-demo get pods -l app=bad-deploy -o wide --sort-by=.metadata.name || true
    echo
    echo "## service-controller"
    kubectl -n "${SYSTEM_NAMESPACE}" get pods -l app="${SYSTEM_DEPLOYMENT_NAME}" -o wide --sort-by=.metadata.name || true
  } >"${output_path}"
}

run_once() {
  local run_number="$1"
  local run_dir="${EVIDENCE_DIR}/run-$(printf '%02d' "${run_number}")"
  local run_failed=0
  local incident_id=""
  local action_id=""
  local status_first=""
  local status_retry=""
  local status_restart_retry=""

  mkdir -p "${run_dir}"
  echo "=== run ${run_number}/${RUNS} ==="

  kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f - >"${run_dir}/ns-apply.txt"
  kubectl apply -f "${SCENARIO_MANIFEST}" >"${run_dir}/scenario-apply.txt"

  snapshot_cluster_state "${run_dir}/cluster-before.txt"

  curl_with_retry "POST" "${SERVICE_URL}/webhooks/alertmanager" "${run_dir}/webhook-response.json" \
    -H 'Content-Type: application/json' \
    --data @"${ALERT_PAYLOAD}" || run_failed=1

  incident_id="$(jq -r '.incident_id // empty' "${run_dir}/webhook-response.json" 2>/dev/null || true)"
  action_id="$(jq -r '.action_ids[0] // empty' "${run_dir}/webhook-response.json" 2>/dev/null || true)"

  if [[ -z "${incident_id}" ]]; then
    echo "missing incident_id in webhook response" >"${run_dir}/error.txt"
    run_failed=1
  fi

  if [[ -n "${incident_id}" ]]; then
    curl_with_retry "GET" "${SERVICE_URL}/incidents/${incident_id}" "${run_dir}/incident-readback.json" || run_failed=1
  fi

  if [[ "${REQUIRE_ACTION_ID}" == "1" && -z "${action_id}" ]]; then
    echo "missing action_id in webhook response" >>"${run_dir}/error.txt"
    run_failed=1
  fi

  if [[ -n "${action_id}" ]]; then
    curl_with_retry "POST" "${SERVICE_URL}/actions/${action_id}/approve" "${run_dir}/approval-first.json" \
      -H "Authorization: Bearer ${OPERATOR_API_TOKEN}" \
      -H 'Content-Type: application/json' || run_failed=1
    status_first="$(jq -r '.status // empty' "${run_dir}/approval-first.json" 2>/dev/null || true)"

    curl_with_retry "POST" "${SERVICE_URL}/actions/${action_id}/approve" "${run_dir}/approval-retry.json" \
      -H "Authorization: Bearer ${OPERATOR_API_TOKEN}" \
      -H 'Content-Type: application/json' || run_failed=1
    status_retry="$(jq -r '.status // empty' "${run_dir}/approval-retry.json" 2>/dev/null || true)"

    if [[ "${RUN_RESTART_CHECK}" == "1" ]]; then
      kubectl -n "${SYSTEM_NAMESPACE}" rollout restart "deployment/${SYSTEM_DEPLOYMENT_NAME}" >"${run_dir}/service-rollout-restart.txt"
      kubectl -n "${SYSTEM_NAMESPACE}" rollout status "deployment/${SYSTEM_DEPLOYMENT_NAME}" --timeout=180s >"${run_dir}/service-rollout-status.txt"
      curl_with_retry "POST" "${SERVICE_URL}/actions/${action_id}/approve" "${run_dir}/approval-post-restart-retry.json" \
        -H "Authorization: Bearer ${OPERATOR_API_TOKEN}" \
        -H 'Content-Type: application/json' || run_failed=1
      status_restart_retry="$(jq -r '.status // empty' "${run_dir}/approval-post-restart-retry.json" 2>/dev/null || true)"
    fi
  fi

  snapshot_cluster_state "${run_dir}/cluster-after.txt"
  diff -u "${run_dir}/cluster-before.txt" "${run_dir}/cluster-after.txt" >"${run_dir}/cluster-diff.txt" || true
  kubectl -n "${SYSTEM_NAMESPACE}" logs "deployment/${SYSTEM_DEPLOYMENT_NAME}" --since=15m >"${run_dir}/service.log" || true

  {
    echo "{"
    echo "  \"run\": ${run_number},"
    echo "  \"incident_id\": \"${incident_id}\","
    echo "  \"action_id\": \"${action_id}\","
    echo "  \"status_first\": \"${status_first}\","
    echo "  \"status_retry\": \"${status_retry}\","
    echo "  \"status_post_restart_retry\": \"${status_restart_retry}\","
    echo "  \"run_failed\": ${run_failed}"
    echo "}"
  } >"${run_dir}/summary.json"

  jq -c . "${run_dir}/summary.json" >>"${EVIDENCE_DIR}/runs.jsonl"
}

mkdir -p "${EVIDENCE_DIR}"
echo "# k8s-ai-sre reliability evidence" >"${EVIDENCE_DIR}/README.md"
echo "" >>"${EVIDENCE_DIR}/README.md"
echo "- generated_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"${EVIDENCE_DIR}/README.md"
echo "- runs: ${RUNS}" >>"${EVIDENCE_DIR}/README.md"
echo "- service_url: ${SERVICE_URL}" >>"${EVIDENCE_DIR}/README.md"
echo "- restart_check: ${RUN_RESTART_CHECK}" >>"${EVIDENCE_DIR}/README.md"
echo "- require_action_id: ${REQUIRE_ACTION_ID}" >>"${EVIDENCE_DIR}/README.md"
echo "- evidence layout: run-XX/{webhook-response.json,incident-readback.json,approval-*.json,cluster-*.txt,cluster-diff.txt,service.log,summary.json}" >>"${EVIDENCE_DIR}/README.md"

if ! ensure_service_ready; then
  echo "Service is not reachable at ${SERVICE_URL}"
  exit 1
fi

for run in $(seq 1 "${RUNS}"); do
  run_once "${run}"
done

jq -s '
  {
    total_runs: length,
    failed_runs: (map(select(.run_failed == 1)) | length),
    missing_action_runs: (map(select(.action_id == "")) | length),
    retry_status_mismatch_runs: (map(select(.action_id != "" and .status_first != .status_retry)) | length),
    restart_retry_status_mismatch_runs: (map(select(.action_id != "" and .status_post_restart_retry != "" and .status_first != .status_post_restart_retry)) | length),
    runs: .
  }
' "${EVIDENCE_DIR}/runs.jsonl" >"${EVIDENCE_DIR}/summary.json"

jq -r '
  "run\tincident_id\taction_id\tstatus_first\tstatus_retry\tstatus_post_restart_retry\trun_failed",
  (.runs[] | [
    (.run|tostring),
    .incident_id,
    .action_id,
    .status_first,
    .status_retry,
    .status_post_restart_retry,
    (.run_failed|tostring)
  ] | @tsv)
' "${EVIDENCE_DIR}/summary.json" >"${EVIDENCE_DIR}/summary.tsv"

echo
echo "Reliability evidence saved at: ${EVIDENCE_DIR}"
jq . "${EVIDENCE_DIR}/summary.json"

FAILED_RUNS="$(jq -r '.failed_runs' "${EVIDENCE_DIR}/summary.json")"
RETRY_MISMATCH="$(jq -r '.retry_status_mismatch_runs' "${EVIDENCE_DIR}/summary.json")"
RESTART_RETRY_MISMATCH="$(jq -r '.restart_retry_status_mismatch_runs' "${EVIDENCE_DIR}/summary.json")"
MISSING_ACTION_RUNS="$(jq -r '.missing_action_runs' "${EVIDENCE_DIR}/summary.json")"

if [[ "${FAILED_RUNS}" != "0" || "${RETRY_MISMATCH}" != "0" || "${RESTART_RETRY_MISMATCH}" != "0" || "${MISSING_ACTION_RUNS}" != "0" ]]; then
  echo "Reliability check failed. Review ${EVIDENCE_DIR}/summary.json."
  exit 1
fi

echo "Reliability check passed with ${RUNS}/${RUNS} successful runs."
