# Testing Guide

This file describes how to test the project in its current state. It should evolve as the implementation changes, instead of keeping separate test sections for every historical step.

## Current Scope

The app currently supports:
- a real `kubectl`-backed pod lookup tool
- a real generic `kubectl`-backed resource lookup tool
- real evidence tools for listing resources, events, and pod logs
- a workload-level helper for finding pods owned by a deployment
- an SRE-oriented response format
- CLI target selection in the form `<kind> <namespace> <name>`
- a small module layout:
  - `main.py`
  - `tools.py`
  - `prompts.py`

The default demo investigation target is:
- `Deployment bad-deploy` in namespace `ai-sre-demo`

## Prerequisites

- a local kind cluster is running
- your kube context points to that cluster
- required model environment variables are available

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

## What To Verify

For the current implementation, verify:
- the app runs successfully
- the agent uses the expected tools for the current demo target
- the tools read real data from `kubectl`
- custom CLI targets work without editing code
- for the deployment scenario, the investigation may use:
  - `get_k8s_resource`
  - `list_k8s_resources`
  - `get_workload_pods`
  - `get_k8s_resource_events`
  - `get_pod_logs`
- the final answer uses this response format:
  - `Summary:`
  - `Most likely cause:`
  - `Next actions:`
- the answer reflects the real cluster symptom instead of generic Kubernetes advice
- the answer should improve if the model inspects related pods in addition to the deployment object

## Useful Manual Checks

Inspect the current demo target directly with `kubectl`:

For the pod scenario:

```bash
kubectl get pod crashy -n ai-sre-demo -o json
uv run main.py pod ai-sre-demo crashy
```

For the deployment scenario:

```bash
kubectl get deployment bad-deploy -n ai-sre-demo -o json
kubectl get pods -n ai-sre-demo -l app=bad-deploy -o wide
kubectl get events -n ai-sre-demo --field-selector involvedObject.kind=Pod
uv run main.py deployment ai-sre-demo bad-deploy
```

## Cleanup

Delete the test namespace when you are done:

```bash
kubectl delete namespace ai-sre-demo
```
