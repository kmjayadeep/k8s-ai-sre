# Testing

The canonical validation runbook lives in `TESTING.md`. Use this page as a docs-site entry point.

## Covered flows

- local service and `/investigate`
- local service and Alertmanager webhook ingestion
- Telegram approval loop (`/incident`, `/status`, `/approve`, `/reject`)
- kind-based end-to-end exercise

## CI And Local Baseline

```bash
uv run python -m unittest tests.test_ci_smoke_api_contract
uv run python -m unittest discover -s tests
```

Current `main` runs three validation lanes in `.github/workflows/tests.yml`:

- smoke API contract checks for fast failure feedback
- full Python test discovery for the baseline suite
- manifest validation for Helm and Kustomize output

When you change docs, also run:

```bash
uv tool run --with mkdocs mkdocs build --strict
```

## E2E helper scripts

```bash
# Quick investigate + approve flow
scripts/e2e_kind.sh

# P0 reliability gate: repeated N-run validation (RUNS>=5)
scripts/e2e_reliability_kind.sh

# Full in-cluster stack: PrometheusRule + Alertmanager + webhook
scripts/e2e_full_stack_kind.sh
```

The quick helper sends a sample webhook and writes incident output to:

```text
/tmp/k8s-ai-sre-e2e-incident.json
```

For exact prerequisites, verification points, and cleanup commands, follow `TESTING.md` directly.
