# Testing Guide

This file describes how to test the project in its current state. It should evolve as the implementation changes, instead of keeping separate test sections for every historical step.

## Current Scope

The app currently supports:
- a real `kubectl`-backed pod lookup tool
- a real generic `kubectl`-backed resource lookup tool
- an SRE-oriented response format

The current demo investigation target in is:
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

```bash
uv run main.py
```

## What To Verify

For the current implementation, verify:
- the app runs successfully
- the agent uses the expected tool for the current demo target
- the tool reads real data from `kubectl`
- the final answer uses this response format:
  - `Summary:`
  - `Most likely cause:`
  - `Next actions:`
- the answer reflects the real cluster symptom instead of generic Kubernetes advice

## Useful Manual Checks

Inspect the current demo target directly with `kubectl`:

For the pod scenario:

```bash
kubectl get pod crashy -n ai-sre-demo -o json
```

For the deployment scenario:

```bash
kubectl get deployment bad-deploy -n ai-sre-demo -o json
kubectl get pods -n ai-sre-demo -l app=bad-deploy -o wide
```

## Cleanup

Delete the test namespace when you are done:

```bash
kubectl delete namespace ai-sre-demo
```
