# Incremental Build Plan

This project will be built in small, locally testable steps. The goal is to avoid large jumps in complexity and keep every stage understandable and runnable.

## Goal

Build from the current boilerplate to an AI Kubernetes SRE agent in controlled layers:

1. local single-tool agent with real cluster reads
2. local multi-tool investigator with real evidence
3. local operator workflow with approvals
4. webhook-driven service
5. Telegram integration
6. in-cluster deployment

## Rules For Implementation

- Add one new concept at a time.
- Each step must remain runnable locally.
- Each step must have a simple manual verification path.
- Keep the code small until the behavior is proven.
- Prefer read-only integrations first, then add approvals, then add write actions.
- Prefer generic Kubernetes resource interfaces over resource-specific tool APIs where possible, so custom resources can fit naturally later.
- Use the local `kubectl` context as the first real integration path before introducing in-cluster auth or larger client abstractions.

## Tool Design Principle

The long-term tool interface should be generic enough to support both built-in Kubernetes resources and CRDs.

Preferred shape:

- `get_k8s_resource(api_version, kind, namespace, name)`
- `list_k8s_resources(api_version, kind, namespace=None, label_selector=None)`
- `get_k8s_resource_events(kind, namespace, name)`
- `get_pod_logs(namespace, pod_name, container=None)`

Notes:
- `api_version + kind + namespace + name` should be the core resource identity model.
- This keeps the interface compatible with custom resources such as Argo Rollouts, CertManager resources, Crossplane resources, and operator-managed objects.
- Pod logs remain a special-case tool because log access is not a generic resource capability.
- Resource-specific helper tools can still exist later, but they should be wrappers around the generic resource access layer rather than the primary design.

## Step 0: Freeze The Baseline

Current state:
- `main.py` runs a toy assistant
- `model_factory.py` creates the model
- one demo tool exists

Verification:
- `uv run main.py`

## Step 1: Replace Weather With One Real Pod Read Tool

Change:
- remove the weather tool
- add `get_pod_status(namespace: str, pod_name: str) -> str`
- implement it using local `kubectl`
- return a compact summary containing:
  - phase
  - restart count
  - waiting or terminated reason if present
  - node name if present

Implementation note:
- use `subprocess` to call `kubectl get pod -n <namespace> <pod_name> -o json`
- do not introduce a full Kubernetes Python client yet

Goal:
- prove the agent can read real cluster state immediately

Verification:
- `uv run main.py`
- investigate one real pod from your cluster

## Step 2: Make The Agent An SRE Investigator

Change:
- rename the agent to reflect SRE behavior
- update instructions so it:
  - gathers evidence from tools
  - explains likely causes
  - proposes next actions

Goal:
- make the behavior incident-focused instead of generic assistant behavior

Verification:
- inspect the output format and confirm it includes summary, likely cause, and next steps

## Step 3: Introduce A Generic Real Kubernetes Resource Tool

Change:
- add a generic tool:
  - `get_k8s_resource(api_version, kind, namespace, name) -> str`
- implement it with `kubectl get`
- support at least:
  - `Pod`
  - `Deployment`
  - one real CRD if your cluster has one
- keep `get_pod_status(...)` as a thin wrapper over the generic path where practical

Goal:
- establish a CRD-friendly tool interface using real cluster access

Verification:
- investigate one built-in resource
- investigate one custom resource if available

## Step 4: Add Real Evidence Tools

Change:
- add:
  - `list_k8s_resources`
  - `get_k8s_resource_events`
  - `get_pod_logs`
- implement each with `kubectl`

Goal:
- let the agent combine multiple real evidence sources

Verification:
- investigate a real failing pod or workload and confirm the agent uses more than one tool

## Step 5: Refactor Into Small Modules

Change:
- split into a minimal file layout:
  - `main.py`
  - `model_factory.py`
  - `tools.py`
  - optional `prompts.py`

Goal:
- improve readability without introducing service complexity

Verification:
- `uv run main.py`

## Step 6: Add A Configurable Local Investigation Target

Change:
- allow the target namespace and resource name to be passed in more easily
- simplest options:
  - constants at the top of `main.py`
  - or CLI arguments

Goal:
- test against real cluster objects without editing deeper code paths every time

Verification:
- investigate multiple real resources in separate runs

## Step 7: Add Workload-Level Reads

Change:
- add tools for:
  - deployment or statefulset status
  - listing related pods
  - rollout condition inspection
- support CRDs later through the generic resource path

Goal:
- support deployment-level investigation instead of only pod-level investigation

Verification:
- investigate one unhealthy deployment

## Step 8: Add Prometheus Reads

Change:
- add one Prometheus client
- start with a small set of fixed queries, such as:
  - restart increase
  - unready pods

Goal:
- combine metrics with Kubernetes state

Verification:
- run one scenario where metrics improve the diagnosis

## Step 9: Add A Python Investigation Orchestrator

Change:
- add a function like `investigate_workload(namespace, workload)`
- collect evidence in Python first
- send the structured evidence bundle to the model afterward

Goal:
- make the behavior easier to reason about than fully agent-driven tool selection

Verification:
- print or inspect the evidence bundle before synthesis

## Step 10: Add A Local Interactive CLI

Change:
- replace the one hardcoded prompt with a small input loop
- support commands like:
  - `investigate pod <namespace> <pod>`
  - `investigate deploy <namespace> <name>`
  - `investigate resource <api_version> <kind> <namespace> <name>`
  - `ask <question>`

Goal:
- allow repeated local testing without editing code

Verification:
- run multiple investigations in one session

## Step 11: Add Remediation Proposals Only

Change:
- return:
  - likely cause
  - confidence
  - recommended next actions
- still no write execution

Goal:
- separate diagnosis from action

Verification:
- confirm recommendations are concrete and evidence-based

## Step 12: Add One Local Guarded Action

Change:
- add exactly one write action, likely:
  - `delete_pod`
  or
  - `rollout_restart`
- execute it through `kubectl`
- require explicit local confirmation before execution

Goal:
- introduce human-in-the-loop remediation with minimal risk

Verification:
- propose action, confirm locally, execute against a safe target

## Step 13: Add Local Approval Flow

Change:
- assign action IDs
- add local commands:
  - `approve <action-id>`
  - `reject <action-id>`

Goal:
- stabilize the approval model before Telegram integration

Verification:
- confirm approvals and rejections update action state correctly

## Step 14: Add A Minimal HTTP Server

Change:
- add a very small service with:
  - `GET /healthz`
  - `POST /investigate`

Goal:
- run the agent as a service before adding alert-specific behavior

Verification:
- `curl` a request and receive an investigation response

## Step 15: Add Alertmanager Webhook Support

Change:
- add `POST /webhooks/alertmanager`
- parse only the alert fields needed for v1

Goal:
- make investigations event-driven

Verification:
- send a saved sample Alertmanager payload locally

## Step 16: Add Incident State Storage

Change:
- add a store abstraction
- start with in-memory
- later add Redis behind the same interface

Goal:
- keep incident and report state available after investigation starts

Verification:
- trigger an alert, then fetch or inspect stored incident data

## Step 17: Add Telegram Notifications Only

Change:
- send summaries to Telegram
- no commands yet

Goal:
- establish outbound operator communication first

Verification:
- trigger an alert and confirm the Telegram message arrives

## Step 18: Add Read-Only Telegram Commands

Change:
- support commands such as:
  - `/incident <id>`
  - `/ask <id> <question>`

Goal:
- let operators inspect and ask follow-up questions from chat

Verification:
- retrieve an incident report and ask a follow-up question

## Step 19: Add Telegram Approval For One Action

Change:
- support:
  - `/approve <incident_id> <action_id>`

Goal:
- complete the chat-based human approval loop

Verification:
- receive an action proposal in Telegram and approve it successfully

## Step 20: Add Safety Controls

Change:
- enforce:
  - allowed write namespaces
  - allowed Telegram users or chats
  - action expiry
  - allowed action kinds only

Goal:
- fail closed before cluster deployment

Verification:
- confirm disallowed requests are rejected cleanly

## Step 21: Add Container And Kubernetes Manifests

Change:
- add:
  - Dockerfile
  - Deployment
  - ServiceAccount
  - RBAC

Goal:
- move from local tool to cluster service

Verification:
- deploy to a dev cluster and check health endpoints

## Step 22: Support Local And In-Cluster Auth

Change:
- use local `kubectl` or kubeconfig for development
- use service account credentials in-cluster
- centralize config handling

Goal:
- run the same app in both environments with config changes only

Verification:
- run locally and in-cluster without code changes

## Step 23: Add Service Observability

Change:
- add structured logs for:
  - alert received
  - investigation started
  - investigation completed
  - action approved
  - action executed
  - action failed

Goal:
- make the agent itself debuggable and operable

Verification:
- inspect logs for one full incident flow

## Step 24: Expand The Action Set Carefully

Only after the first action is stable, add more:
- `rollout_restart`
- `scale`
- optionally `rollout_undo`

Goal:
- expand usefulness without taking on too much operational risk too early

Verification:
- test each new action independently in a safe environment

## Milestone Grouping

### Milestone 1: Real Cluster Read Prototype
- Steps 1 to 6

### Milestone 2: Real Read-Only Cluster Investigator
- Steps 7 to 11

### Milestone 3: Local Operator Workflow
- Steps 12 to 13

### Milestone 4: Service, Alerts, And Chat
- Steps 14 to 19

### Milestone 5: Safety And Deployment
- Steps 20 to 24

## Recommended Next Step

Implement only Step 1 next:
- replace the weather tool with a real `get_pod_status` tool
- read pod data using local `kubectl`
- keep everything else unchanged
- verify locally with `uv run main.py`
