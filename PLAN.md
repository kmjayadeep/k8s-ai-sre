# Incremental Build Plan

This project will be built in small, locally testable steps. The goal is to avoid large jumps in complexity and keep every stage understandable and runnable.

## Goal

Build from the current boilerplate to an AI Kubernetes SRE agent in controlled layers:

1. local single-tool agent
2. local multi-tool investigator
3. local webhook-driven service
4. local chat and approval loop
5. in-cluster deployment

## Rules For Implementation

- Add one new concept at a time.
- Each step must remain runnable locally.
- Each step must have a simple manual verification path.
- Keep the code small until the behavior is proven.
- Prefer read-only integrations first, then add approvals, then add write actions.
- Prefer generic Kubernetes resource interfaces over resource-specific tool APIs where possible, so custom resources can fit naturally later.

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

## Step 1: Replace Weather With One Fake Kubernetes Tool

Change:
- remove the weather tool
- add one fake Kubernetes investigation tool
- for the very first step, keep it simple and pod-focused:
  - `get_pod_status(namespace: str, pod_name: str) -> str`
- internally, treat this as a temporary stepping stone toward a generic resource interface
- return hardcoded pod data such as:
  - pod phase
  - restart count
  - waiting reason
  - short recent event summary

Goal:
- introduce Kubernetes-shaped investigation without real cluster access

Verification:
- `uv run main.py`
- prompt the agent to investigate one fake pod

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

## Step 3: Introduce A Generic Fake Kubernetes Resource Tool

Change:
- add a generic fake tool:
  - `get_k8s_resource(api_version, kind, namespace, name) -> str`
- support at least:
  - `Pod`
  - `Deployment`
  - one example CRD shape such as `Rollout`
- keep the returned data hardcoded but realistic
- make resource-specific investigation helpers call this generic layer where possible

Goal:
- establish a CRD-friendly tool interface before real Kubernetes integration

Verification:
- run prompts against both a built-in resource and a fake custom resource
- confirm the agent can reason over both using the same core lookup shape

## Step 4: Add More Fake SRE Tools

Change:
- add fake tools such as:
  - `list_k8s_resources`
  - `get_k8s_resource_events`
  - `get_pod_logs`
- where useful, add resource-specific convenience wrappers that sit on top of the generic layer

Goal:
- let the agent combine multiple evidence sources before adding real integrations

Verification:
- run a fake deployment failure scenario and confirm the agent uses more than one tool

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

## Step 6: Add Local Incident Scenarios

Change:
- add a few selectable fake scenarios:
  - crash loop
  - image pull error
  - pending pod
  - custom resource degraded state

Goal:
- make local testing repeatable across different failure types

Verification:
- run multiple scenarios and compare agent output

## Step 7: Add One Real Kubernetes Read Tool

Change:
- introduce Kubernetes client access
- replace only one fake tool first
- prefer implementing the real generic lookup path:
  - `get_k8s_resource(api_version, kind, namespace, name)`
- make pod-specific helpers call into that path where appropriate

Goal:
- move from toy investigation to one real cluster read path

Verification:
- run locally against a real kubeconfig
- investigate one real built-in resource
- fetch one real CRD if available

## Step 8: Add Real Logs And Events

Change:
- add real read-only tools for:
  - pod logs
  - recent object events

Goal:
- support useful pod-level investigation

Verification:
- investigate a real failing pod and confirm the response uses logs and events

## Step 9: Add Workload-Level Reads

Change:
- add tools for:
  - listing resources by kind
  - finding related workloads
  - rollout or controller condition inspection
- support both built-in controllers and selected CRDs where practical

Goal:
- support deployment-level investigation instead of only pod-level investigation

Verification:
- investigate one unhealthy deployment

## Step 10: Add Prometheus Reads

Change:
- add one Prometheus client
- start with a small set of fixed queries, such as:
  - restart increase
  - unready pods

Goal:
- combine metrics with Kubernetes state

Verification:
- run one scenario where metrics improve the diagnosis

## Step 11: Add A Python Investigation Orchestrator

Change:
- add a function like `investigate_workload(namespace, workload)`
- collect evidence in Python first
- send the structured evidence bundle to the model afterward

Goal:
- make the behavior easier to reason about than fully agent-driven tool selection

Verification:
- print or inspect the evidence bundle before synthesis

## Step 12: Add A Local Interactive CLI

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

## Step 13: Add Remediation Proposals Only

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

## Step 14: Add One Local Guarded Action

Change:
- add exactly one write action, likely:
  - `delete_pod`
  or
  - `rollout_restart`
- require explicit local confirmation before execution

Goal:
- introduce human-in-the-loop remediation with minimal risk

Verification:
- propose action, confirm locally, execute against a safe target

## Step 15: Add Local Approval Flow

Change:
- assign action IDs
- add local commands:
  - `approve <action-id>`
  - `reject <action-id>`

Goal:
- stabilize the approval model before Telegram integration

Verification:
- confirm approvals and rejections update action state correctly

## Step 16: Add A Minimal HTTP Server

Change:
- add a very small service with:
  - `GET /healthz`
  - `POST /investigate`

Goal:
- run the agent as a service before adding alert-specific behavior

Verification:
- `curl` a request and receive an investigation response

## Step 17: Add Alertmanager Webhook Support

Change:
- add `POST /webhooks/alertmanager`
- parse only the alert fields needed for v1

Goal:
- make investigations event-driven

Verification:
- send a saved sample Alertmanager payload locally

## Step 18: Add Incident State Storage

Change:
- add a store abstraction
- start with in-memory
- later add Redis behind the same interface

Goal:
- keep incident and report state available after investigation starts

Verification:
- trigger an alert, then fetch or inspect stored incident data

## Step 19: Add Telegram Notifications Only

Change:
- send summaries to Telegram
- no commands yet

Goal:
- establish outbound operator communication first

Verification:
- trigger an alert and confirm the Telegram message arrives

## Step 20: Add Read-Only Telegram Commands

Change:
- support commands such as:
  - `/incident <id>`
  - `/ask <id> <question>`

Goal:
- let operators inspect and ask follow-up questions from chat

Verification:
- retrieve an incident report and ask a follow-up question

## Step 21: Add Telegram Approval For One Action

Change:
- support:
  - `/approve <incident_id> <action_id>`

Goal:
- complete the chat-based human approval loop

Verification:
- receive an action proposal in Telegram and approve it successfully

## Step 22: Add Safety Controls

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

## Step 23: Add Container And Kubernetes Manifests

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

## Step 24: Support Local And In-Cluster Auth

Change:
- use kubeconfig locally
- use service account credentials in-cluster
- centralize config handling

Goal:
- run the same app in both environments with config changes only

Verification:
- run locally and in-cluster without code changes

## Step 25: Add Service Observability

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

## Step 26: Expand The Action Set Carefully

Only after the first action is stable, add more:
- `rollout_restart`
- `scale`
- optionally `rollout_undo`

Goal:
- expand usefulness without taking on too much operational risk too early

Verification:
- test each new action independently in a safe environment

## Milestone Grouping

### Milestone 1: Local Reasoning Prototype
- Steps 1 to 6

### Milestone 2: Real Read-Only Cluster Investigator
- Steps 7 to 11

### Milestone 3: Local Operator Workflow
- Steps 12 to 15

### Milestone 4: Service, Alerts, And Chat
- Steps 16 to 21

### Milestone 5: Safety And Deployment
- Steps 22 to 26

## Recommended Next Step

Implement only Step 1 next:
- replace the weather tool with a fake Kubernetes pod-status tool
- keep everything else unchanged
- verify locally with `uv run main.py`
