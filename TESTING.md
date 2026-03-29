# Testing Guide

This file describes how to test the project in its current state. It should evolve as the implementation changes, instead of keeping separate test sections for every historical step.

## Current Scope

The app currently supports:
- a real `kubectl`-backed pod lookup tool
- a real generic `kubectl`-backed resource lookup tool
- real evidence tools for listing resources, events, and pod logs
- a workload-level helper for finding pods owned by a deployment
- an optional Prometheus query tool controlled by `PROMETHEUS_BASE_URL`
- an SRE-oriented response format
- CLI target selection in the form `<kind> <namespace> <name>`
- a Python evidence collection step before the model response
- one guarded local action: `delete-pod`
- a local approval flow with action IDs for pod deletion
- a minimal local HTTP server with `/healthz` and `/investigate`
- an Alertmanager-compatible webhook endpoint
- a JSON-backed local incident store with `GET /incidents/{incident_id}`
- optional outbound Telegram notifications on new incidents
- read-only Telegram commands via `telegram-poll`
- Telegram approval and rejection for existing action IDs
- basic safety controls for writes and Telegram access
- a container image and Kubernetes deployment manifest
- structured JSON logs for key lifecycle events via `loguru`
- the image includes `kubectl` so the same kubectl-backed runtime can work in-cluster
- a GitHub Actions workflow to build and push the image to GHCR
- a small module layout:
  - `main.py`
  - `investigate.py`
  - `server.py`
  - `incident_store.py`
  - `telegram_bot.py`
  - `notifier.py`
  - `action_store.py`
  - `logger.py`
  - `tools.py`
  - `prompts.py`
  - `Dockerfile`
  - `.github/workflows/container.yml`
  - `deploy/k8s-ai-sre.yaml`

The default demo investigation target is:
- `Deployment bad-deploy` in namespace `ai-sre-demo`

## Prerequisites

- a local kind cluster is running
- your kube context points to that cluster
- required model environment variables are available
- optional: `PROMETHEUS_BASE_URL` if you want metrics queries enabled
- optional: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` if you want Telegram notifications
- optional: `WRITE_ALLOWED_NAMESPACES` to restrict write actions
- optional: `TELEGRAM_ALLOWED_CHAT_IDS` to restrict bot command handling

Check cluster access:

```bash
kubectl config current-context
kubectl get nodes
```

## Test Environment Setup

Create the namespace if it does not already exist:

```bash
kubectl create namespace ai-sre-demo
```

## Scenario 1: Crash-Looping Pod

Create a pod that repeatedly crashes:

```bash
kubectl apply -n ai-sre-demo -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: crashy
spec:
  containers:
    - name: crashy
      image: busybox:1.36
      command: ["sh", "-c", "echo crashing; sleep 2; exit 1"]
EOF
```

Watch it:

```bash
kubectl get pod crashy -n ai-sre-demo -w
```

Expected symptom:
- repeated restarts
- likely `CrashLoopBackOff`

Use this scenario when the current code path investigates a pod.

## Scenario 2: Unhealthy Deployment

Create a deployment with a broken image:

```bash
kubectl apply -n ai-sre-demo -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bad-deploy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bad-deploy
  template:
    metadata:
      labels:
        app: bad-deploy
    spec:
      containers:
        - name: app
          image: nginx:does-not-exist
EOF
```

Check status:

```bash
kubectl get deployment bad-deploy -n ai-sre-demo
kubectl get pods -n ai-sre-demo -l app=bad-deploy
```

Expected symptom:
- deployment does not become healthy
- related pod shows image pull failure

Use this scenario when the current code path investigates a deployment or generic resource.

## Run The App

Default target:

```bash
uv run main.py
```

Custom target:

```bash
uv run main.py pod ai-sre-demo crashy
```

Argument format:

```bash
uv run main.py <kind> <namespace> <name>
```

Guarded action format:

```bash
uv run main.py delete-pod <namespace> <pod-name> --confirm
```

Approval flow:

```bash
uv run main.py propose-delete-pod <namespace> <pod-name>
uv run main.py approve <action-id>
uv run main.py reject <action-id>
```

HTTP server:

```bash
uv sync
uv run main.py serve
```

Telegram polling:

```bash
uv run main.py telegram-poll
```

## What To Verify

For the current implementation, verify:
- the app runs successfully
- the app prints a collected evidence bundle before the final answer
- the agent uses the expected tools for the current demo target
- the tools read real data from `kubectl`
- custom CLI targets work without editing code
- for the deployment scenario, the investigation may use:
  - `get_k8s_resource`
  - `list_k8s_resources`
  - `get_workload_pods`
  - `get_k8s_resource_events`
  - `get_pod_logs`
  - `query_prometheus`
- the final answer uses this response format:
  - `Summary:`
  - `Most likely cause:`
  - `Confidence:`
  - `Proposed actions:`
- the answer reflects the real cluster symptom instead of generic Kubernetes advice
- the answer should improve if the model inspects related pods in addition to the deployment object
- the final answer should be grounded in the printed evidence bundle
- the answer must not claim it already executed a remediation
- proposed actions should be concrete operator actions, not vague advice
- pod deletion requires explicit `--confirm`
- approval commands should work with generated action IDs
- the HTTP server should answer `GET /healthz`
- the HTTP server should accept `POST /investigate`
- the HTTP server should accept `POST /webhooks/alertmanager`
- the HTTP server should allow incident lookup with `GET /incidents/{incident_id}`
- incident data should be written to `/tmp/k8s-ai-sre-incidents.json`
- if Telegram is configured, new incidents should send one outbound notification
- read-only Telegram commands should reply with stored incident data
- Telegram should support `/approve <action-id>` and `/reject <action-id>` for existing pending actions
- write actions should fail closed outside allowed namespaces
- actions should expire after a short time
- Telegram command handling should ignore unauthorized chat IDs when configured
- the app should be buildable into a container image
- the app should be deployable to the cluster with the provided manifest
- the app should emit structured logs for key events
- local execution should use your kubeconfig-backed `kubectl`
- in-cluster execution should use service-account-backed `kubectl`
- pushes to `main` should build and publish the image to GHCR

If Prometheus is not configured:
- the app should still run normally
- the Prometheus tool should fail gracefully if the model tries to use it

If Prometheus is configured:
- the model may use metrics as additional evidence
- metrics should supplement Kubernetes evidence, not replace it

If Telegram is not configured:
- incident creation should still work
- the response should report that Telegram is not configured

If Telegram is configured:
- incident creation should send one outbound notification
- the response should include notification status
- `/incident <incident-id>` should return the stored answer
- `/status <incident-id>` should return basic stored metadata
- `/approve <action-id>` should execute a pending delete-pod action
- `/reject <action-id>` should reject a pending action

If safety controls are configured:
- `WRITE_ALLOWED_NAMESPACES` should restrict delete actions
- `TELEGRAM_ALLOWED_CHAT_IDS` should restrict Telegram command handling

## Useful Manual Checks

Inspect the current demo target directly with `kubectl`:

For the pod scenario:

```bash
kubectl get pod crashy -n ai-sre-demo -o json
uv run main.py pod ai-sre-demo crashy
```

Guarded delete test:

```bash
uv run main.py delete-pod ai-sre-demo crashy
uv run main.py delete-pod ai-sre-demo crashy --confirm
kubectl get pod crashy -n ai-sre-demo
```

Expected behavior:
- without `--confirm`, deletion is refused
- with `--confirm`, the pod is deleted and Kubernetes recreates it only if a controller owns it

Approval flow test:

```bash
uv run main.py propose-delete-pod ai-sre-demo crashy
uv run main.py reject <action-id>
uv run main.py propose-delete-pod ai-sre-demo crashy
uv run main.py approve <action-id>
kubectl get pod crashy -n ai-sre-demo
```

Expected behavior:
- `propose-delete-pod` prints an action ID
- `reject` marks the action as rejected
- `approve` executes the deletion

For the deployment scenario:

```bash
kubectl get deployment bad-deploy -n ai-sre-demo -o json
kubectl get pods -n ai-sre-demo -l app=bad-deploy -o wide
kubectl get events -n ai-sre-demo --field-selector involvedObject.kind=Pod
uv run main.py deployment ai-sre-demo bad-deploy
```


Optional Prometheus-enabled run:

```bash
export PROMETHEUS_BASE_URL=http://localhost:9090
uv run main.py deployment ai-sre-demo bad-deploy
```

HTTP server test:

Start the server:

```bash
uv sync
uv run main.py serve
```

Then in another terminal:

```bash
curl http://127.0.0.1:8080/healthz
curl -X POST http://127.0.0.1:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"bad-deploy"}'
```

Expected behavior:
- `/healthz` returns an `ok` status payload
- `/investigate` returns JSON with:
  - `incident_id`
  - target identity
  - collected evidence
  - final model answer
  - `notification_status`
- the returned `incident_id` can be fetched later from `/incidents/{incident_id}`

Alertmanager webhook test:

```bash
curl -X POST http://127.0.0.1:8080/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  -d '{
    "commonLabels": {
      "namespace": "ai-sre-demo",
      "deployment": "bad-deploy"
    },
    "alerts": [
      {
        "labels": {
          "alertname": "DeploymentNotHealthy"
        }
      }
    ]
  }'
```

Expected behavior:
- the webhook resolves the target from alert labels
- the response includes the same investigation payload shape as `/investigate`
- the response contains `"source": "alertmanager"`

Optional Telegram notification test:

Set:

```bash
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
```

Then call `/investigate` or `/webhooks/alertmanager`.

Expected behavior:
- the response includes `notification_status`
- a Telegram message is sent to the configured chat

Telegram command test:

1. Create an incident through `/investigate` or `/webhooks/alertmanager`
2. Send one of these commands to the bot in Telegram:

```text
/incident <incident-id>
/status <incident-id>
```

3. Poll once:

```bash
uv run main.py telegram-poll
```

Expected behavior:
- the bot replies in Telegram with incident details
- repeated polls do not reprocess the same update because the offset is stored in `/tmp/k8s-ai-sre-telegram-offset.json`

Telegram approval test:

1. Create a pending action:

```bash
uv run main.py propose-delete-pod ai-sre-demo crashy
```

2. Send one of these commands to the bot:

```text
/approve <action-id>
/reject <action-id>
```

3. Poll once:

```bash
uv run main.py telegram-poll
```

Expected behavior:
- `/approve` executes the pending delete-pod action
- `/reject` marks the action as rejected
- repeated `/approve` for the same action should report that it is no longer pending

Safety control test:

```bash
export WRITE_ALLOWED_NAMESPACES=default
uv run main.py delete-pod ai-sre-demo crashy --confirm
```

Expected behavior:
- deletion is refused because `ai-sre-demo` is not allowed

Expiry test:

1. Create a pending action:

```bash
uv run main.py propose-delete-pod ai-sre-demo crashy
```

2. Edit `/tmp/k8s-ai-sre-actions.json` and set the action `expires_at` to an older timestamp
3. Run:

```bash
uv run main.py approve <action-id>
```

Expected behavior:
- the action is marked `expired`
- the delete is not executed

Incident lookup test:

Use the `incident_id` returned by either `/investigate` or `/webhooks/alertmanager`:

```bash
curl http://127.0.0.1:8080/incidents/<incident-id>
```

Expected behavior:
- returns the stored incident payload
- returns `404` for an unknown incident ID
- incident records persist in `/tmp/k8s-ai-sre-incidents.json`

Container build and deploy test:

Build the image:

```bash
docker build -t k8s-ai-sre:dev .
kind load docker-image k8s-ai-sre:dev
```

Deploy:

```bash
kubectl apply -f deploy/k8s-ai-sre.yaml
kubectl get pods -n ai-sre-system
kubectl get svc -n ai-sre-system
```

Expected behavior:
- the deployment pod starts in `ai-sre-system`
- the service is created
- the pod can read cluster data and, if configured, delete pods only in `ai-sre-demo`
- the container image contains `kubectl`

Logging check:

Run any of these:

```bash
uv run main.py deployment ai-sre-demo bad-deploy
uv run main.py propose-delete-pod ai-sre-demo crashy
uv run main.py serve
```

Expected behavior:
- logs are JSON lines
- events include items such as:
  - `investigation_started`
  - `investigation_completed`
  - `action_proposed`
  - `action_approved`
  - `action_rejected`
  - `alertmanager_webhook_received`
  - `telegram_poll_processed`

GitHub Actions GHCR test:

Workflow file:

```text
.github/workflows/container.yml
```

Expected behavior:
- pull requests build the container but do not push
- pushes to `main` build and push to `ghcr.io/kmjayadeep/k8s-ai-sre`
- tags like `v1.0.0` also publish tagged images

## Cleanup

Delete the test namespace when you are done:

```bash
kubectl delete namespace ai-sre-demo
```
