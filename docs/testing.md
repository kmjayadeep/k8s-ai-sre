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

## E2E helper script

```bash
scripts/e2e_kind.sh
```

The helper sends a sample webhook and writes incident output to:

```text
/tmp/k8s-ai-sre-e2e-incident.json
```

For exact prerequisites, verification points, and cleanup commands, follow `TESTING.md` directly.
