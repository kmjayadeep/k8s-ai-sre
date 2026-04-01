#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIO_MANIFEST="${ROOT_DIR}/examples/kind-bad-deploy.yaml"
ALERT_PAYLOAD="${ROOT_DIR}/examples/alertmanager-bad-deploy.json"
SERVICE_URL="${SERVICE_URL:-http://127.0.0.1:8080}"

echo "Preparing cluster scenario..."
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "${SCENARIO_MANIFEST}"

echo
echo "Start the service in another terminal with one of:"
echo "  uv run main.py"
echo "  kubectl port-forward -n ai-sre-system svc/k8s-ai-sre 8080:80"
echo
echo "Then press Enter to continue."
read -r

echo "Sending Alertmanager-style webhook..."
curl -sS -X POST "${SERVICE_URL}/webhooks/alertmanager" \
  -H 'Content-Type: application/json' \
  --data @"${ALERT_PAYLOAD}" | tee /tmp/k8s-ai-sre-e2e-incident.json

echo
echo "Next checks:"
echo "  1. Inspect /tmp/k8s-ai-sre-e2e-incident.json for incident_id, action_ids, and answer."
echo "  2. Confirm Telegram received the incident summary and any proposed action IDs."
echo "  3. Approve one action from Telegram with /approve <action-id>."
echo "  4. Verify the action result in the cluster:"
echo "     kubectl get deployment bad-deploy -n ai-sre-demo"
echo "     kubectl get pods -n ai-sre-demo -l app=bad-deploy"
echo
echo "Optional cleanup:"
echo "  kubectl delete -f ${SCENARIO_MANIFEST}"
