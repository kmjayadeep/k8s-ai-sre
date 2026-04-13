# Developer Guide

Use this page for contributor workflow. For first-time product setup, start with `docs/quickstart.md`.

## Local Development

### Install dependencies

```bash
uv sync
```

### Configure model access

Required:

```bash
export MODEL_NAME=openai/gpt-oss-20b
export MODEL_API_KEY=your-api-key
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.groq.com/openai/v1
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo
```

Portkey remains a supported gateway. Point `MODEL_BASE_URL` at Portkey and keep `MODEL_PROVIDER` set to the provider label you want recorded in traces.

### Create demo scenario

```bash
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f examples/kind-bad-deploy.yaml
```

### Start the service

```bash
uv run main.py
```

### Trigger investigation

Manual endpoint:

```bash
curl -X POST http://127.0.0.1:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"bad-deploy"}'
```

Alertmanager-style webhook:

```bash
curl -X POST http://127.0.0.1:8080/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  --data @examples/alertmanager-bad-deploy.json
```

## Contributor Validation Workflow

Run the smallest validation set that covers your change, but keep the command names consistent with CI:

- Smoke API contract:

```bash
uv run python -m unittest tests.test_ci_smoke_api_contract
```

- Full Python baseline:

```bash
uv run python -m unittest discover -s tests
```

- Manifest validation for `chart/` or `deploy/` changes:

```bash
helm lint chart
helm template k8s-ai-sre ./chart --namespace ai-sre-system > /tmp/chart-rendered.yaml
kustomize build deploy > /tmp/deploy-rendered.yaml
kubeconform -strict -summary -ignore-missing-schemas /tmp/chart-rendered.yaml
kubeconform -strict -summary -ignore-missing-schemas /tmp/deploy-rendered.yaml
```

- Docs validation for `README.md`, `docs/`, `mkdocs.yml`, `PLAN.md`, or `TESTING.md` changes:

```bash
uv tool run --with mkdocs mkdocs build --strict
```

For end-to-end and kind-based validation, use `TESTING.md`.

## PR Handoff Flow

Current repository workflow is:

1. FoundingEngineer (or the implementation owner) opens the PR with a concise summary and the commands already run.
2. QA validates the branch, adds findings, and records manual or environment-specific evidence on the PR.
3. FoundingEngineer updates the branch, answers QA feedback, and posts any replacement evidence when behavior changed.
4. A human reviewer merges after QA is satisfied and required checks are green.

QA evidence should live on the PR itself:

- GitHub checks for automated CI evidence
- PR description or comments for manual validation, kind runs, screenshots, or artifact paths
- concise summaries with links or file paths rather than pasted log dumps

## Expected Response Fields

Investigation creation endpoints return normalized incident payloads including:

- `incident_id`
- `source`
- `answer`
- `action_ids`
- `proposed_actions`
