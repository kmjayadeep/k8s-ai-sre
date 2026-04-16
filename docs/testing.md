# Testing

<div class="page-intro">
  <p>Pick the lightest validation lane that still proves your change. This page is intentionally short: use it to choose a lane, then drop into the repository runbook for the exact command sequence.</p>
</div>

Use this page to choose the right validation lane. For the full contributor flow, start with [Contributing](contributing.md). For local setup and request examples, use [Developer Guide](developer.md). The canonical validation runbook lives in [the repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md).

## Validation lane selector

| Change type | Minimum lane | Start with | Escalate when |
|---|---|---|---|
| docs-only copy, nav, or screenshots | docs build | `uv tool run --with mkdocs mkdocs build --strict` | the change affects examples, commands, or screenshots that need a live check |
| Python logic, HTTP responses, or Telegram behavior | smoke + baseline | `scripts/smoke.sh` then `uv run python -m unittest discover -s tests` | the change touches approval flow, incident rendering, or integration boundaries |
| Helm chart, Kustomize, or deploy manifests | manifest gate | `helm lint chart` plus the render and `kubeconform` steps in `TESTING.md` | the change could alter runtime wiring or cluster behavior |
| local investigate or webhook behavior | example flow | run the relevant local flow in `TESTING.md` | you need evidence of stored incidents, notifications, or action proposals |
| approval loop, kind e2e, or full alert pipeline | end-to-end lane | use the kind scripts in `TESTING.md` | the change crosses service, cluster, and operator boundaries |

## CI lanes at a glance

Current `main` runs three validation lanes in `.github/workflows/tests.yml`:

- smoke API contract + alertmanager approval-loop + Telegram approval protocol checks for fast failure feedback
- full Python test discovery for the baseline suite
- manifest validation for Helm and Kustomize output

Telegram contract regressions run in the baseline lane through `tests/test_telegram_contracts.py`.

Run only those checks locally:

```bash
uv run python -m unittest tests.test_telegram_contracts
```

When you change docs, also run:

```bash
uv tool run --with mkdocs mkdocs build --strict
```

## When To Open `TESTING.md`

Open the full runbook when you need:

- exact command order and prerequisites for Helm, Kustomize, or kind validation
- verification checkpoints for `/investigate`, Alertmanager webhook, or Telegram flows
- artifact paths, cleanup steps, or evidence bundle locations
- repeated reliability or full in-cluster alert-pipeline validation

## Common entry points

```bash
# fast CI-shaped check
scripts/smoke.sh

# full unit baseline
uv run python -m unittest discover -s tests

# quick investigate + approve flow
scripts/e2e_kind.sh

# P0 reliability gate: repeated N-run validation (RUNS>=5)
scripts/e2e_reliability_kind.sh

# full in-cluster stack: PrometheusRule + Alertmanager + webhook
scripts/e2e_full_stack_kind.sh
```

For exact prerequisites, verification points, artifact paths, and cleanup commands, follow [the repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md) directly.
