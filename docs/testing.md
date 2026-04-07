# Testing

The canonical validation runbook lives in `TESTING.md`. Use this page as a docs-site entry point.

## Covered flows

- local service and `/investigate`
- local service and Alertmanager webhook ingestion
- Telegram approval loop (`/incident`, `/status`, `/approve`, `/reject`)
- kind-based end-to-end exercise

## Baseline unit test command

```bash
.venv/bin/python -m unittest discover -s tests
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
