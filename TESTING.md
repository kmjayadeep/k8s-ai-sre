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
- a small module layout:
  - `main.py`
  - `action_store.py`
  - `tools.py`
  - `prompts.py`

The default demo investigation target is:
- `Deployment bad-deploy` in namespace `ai-sre-demo`

## Prerequisites

- a local kind cluster is running
- your kube context points to that cluster
- required model environment variables are available
- optional: `PROMETHEUS_BASE_URL` if you want metrics queries enabled

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

If Prometheus is not configured:
- the app should still run normally
- the Prometheus tool should fail gracefully if the model tries to use it

If Prometheus is configured:
- the model may use metrics as additional evidence
- metrics should supplement Kubernetes evidence, not replace it

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

## Cleanup

Delete the test namespace when you are done:

```bash
kubectl delete namespace ai-sre-demo
```
