# k8s-ai-sre Plan

## Product Goal

AI-assisted Kubernetes incident investigation with guarded remediation. Complete this loop safely:

1. alert or manual request enters the API
2. investigation gathers real cluster evidence
3. agent proposes guarded remediation actions
4. operator approves or rejects
5. approved actions execute with guardrails

## Current Status (April 2026)

**Production-ready core loop:**
- FastAPI investigation + Alertmanager webhook
- Telegram approval flow (`/incident`, `/approve`, `/reject`)
- HTTP operator API for non-interactive approvals
- Guarded actions: delete-pod, rollout-restart, scale, rollout-undo
- SQLite persistence with atomic saves
- Prometheus metrics endpoint
- Deterministic fallback proposals

**Known gaps to address:**

### User Experience
- [x] Make README more engaging for new users (#73)
- [x] Add simple auth for the incident inspector UI (#74)

### Alert Management
- [x] Add API key support for Alertmanager webhook endpoint (#75)
- [ ] Handle alert resolution (skip investigation for resolved alerts)
- [ ] Deduplicate/merge incidents for the same target

### E2E Reliability
- [ ] Improve E2E test to install real Prometheus + Alertmanager
- [ ] Add proper alert pipeline integration test

### Future (Nice to Have)
- HA persistence for multi-replica deployments
- Federation of approval identity with cluster RBAC/OIDC
- Multi-tenant namespace isolation
- Queueing and backpressure for burst protection

## Architecture

| File | Purpose |
|------|---------|
| `main.py` | Service entrypoint |
| `app/http.py` | API routes + incident inspector |
| `app/investigate.py` | Investigation orchestration |
| `app/tools/` | K8s read + write actions |
| `app/telegram.py` | Telegram polling |
| `model_factory.py` | LLM provider wiring |

## Running

```bash
# Local
uv sync
uv run main.py

# Kubernetes
kubectl apply -k deploy
```

## Testing

```bash
uv run python -m unittest discover -s tests
```
