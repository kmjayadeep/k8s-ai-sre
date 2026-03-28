# Testing Guide

This file tracks how to test the project incrementally after each implementation step.

## Step 1: Real Pod Read Via `kubectl`

### Goal

Verify that the agent can read real pod status from the local Kubernetes cluster using `kubectl`.

### Prerequisites

```bash
kind create cluster
```

### Create The Test Scenario

Create a namespace:

```bash
kubectl create namespace ai-sre-demo
kubens ai-sre-demo
```

Create a pod that intentionally crash loops:

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

Watch it until it becomes unhealthy:

```bash
kubectl get pod crashy -n ai-sre-demo -w
```

You should eventually see repeated restarts and likely `CrashLoopBackOff`.

### Run The Agent

```bash
uv run main.py
```

### Expected Result

- the agent calls `get_pod_status`
- the tool reads real pod data through `kubectl`
- the final answer mentions the pod is unhealthy
- the answer should mention restart behavior or crash-loop behavior

### Cleanup

```bash
kubectl delete namespace ai-sre-demo
```
