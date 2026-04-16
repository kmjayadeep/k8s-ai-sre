# AGENTS.md

Guide for agents working on k8s-ai-sre.

## Project overview

AI-assisted Kubernetes incident investigation with guarded remediation. The service completes this loop safely:

1. alert or manual request enters the API
2. investigation gathers real cluster evidence
3. agent proposes guarded remediation actions
4. operator is notified and explicitly approves or rejects
5. approved actions execute with namespace/RBAC guardrails and auditable state

## Architecture

| File/dir | Purpose |
|---|---|
| `main.py` | Service entrypoint |
| `app/http.py` | API routes + incident inspector UI |
| `app/investigate.py` | Investigation orchestration |
| `app/tools/k8s.py` | Kubernetes + Prometheus read helpers |
| `app/tools/actions.py` | Guarded mutating actions |
| `app/telegram.py` | Telegram polling and command handling |
| `app/stores/` | Incident/action store abstraction |
| `model_factory.py` | Model provider wiring |

## Conventions

- Write actions require explicit approval before execution
- Namespace allow-list via `WRITE_ALLOWED_NAMESPACES`
- Actions perform fail-closed `kubectl auth can-i` checks
- Deployment/Pod targets receive deterministic fallback proposals when model omits proposal tool calls
- PRs should be atomic, reviewable by a human, and should not contain multiple independent changes

## Testing

```bash
uv run python -m unittest discover -s tests
```

For E2E flows, see `TESTING.md`.

## Key ports and paths

- Service runs on `PORT` env var (default 8080)
- Kind cluster for E2E: `kubectl config current-context` should show kind cluster
- Demo namespace: `ai-sre-demo`
- System namespace: `ai-sre-system`

## Important notes

- Never commit or push directly to `main` or `master`
- Always rebase, never merge `main` into PR branch
- Do not merge your own work without explicit review
- Track active priorities and follow-ups in Paperclip issues instead of repo plan files
