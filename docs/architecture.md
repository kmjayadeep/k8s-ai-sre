# Architecture

`k8s-ai-sre` is a service-first assistant that combines HTTP ingestion, investigation orchestration, tool access, and guarded action execution.

## Main Components

- `main.py`: server entrypoint
- `app/http.py`: investigation and webhook endpoints
- `app/investigate.py`: orchestration flow
- `app/tools/k8s.py`: Kubernetes and Prometheus read helpers
- `app/tools/actions.py`: guarded write-action helpers
- `app/telegram.py`: Telegram polling and command handling
- `app/stores/`: SQLite-backed key-value stores (default path `/tmp/k8s-ai-sre-store.sqlite3`)
- `model_factory.py`: model client configuration

## End-to-End Flow

1. request enters from `/investigate` or `/webhooks/alertmanager`
2. investigation gathers cluster evidence through read tools
3. model returns findings and optionally proposes actions
4. incident and proposed actions are persisted
5. Telegram can notify and accept approve/reject commands
6. approved actions execute with namespace and action guardrails

## Guarded Actions

Current actions:

- `delete-pod`
- `rollout-restart`
- `scale`
- `rollout-undo`

Guardrails currently enforced include:

- explicit approval required before execution
- namespace allow-list via `WRITE_ALLOWED_NAMESPACES`
- deployment existence checks for `scale` and `rollout-undo`
- non-negative replica checks for `scale`

## Operator Diagnostics

Queue pressure and investigation worker heartbeat are exposed through `GET /queue-status`.

Example payload:

```json
{
  "queue_depth": 2,
  "max_queue_size": 50,
  "active_investigations": 1,
  "max_concurrent_investigations": 5,
  "queue_utilization": 0.04,
  "last_processing_heartbeat_at": "2026-04-23T06:58:01.531275+00:00",
  "last_processing_heartbeat_age_seconds": 3.417,
  "last_processing_target": "deployment/ai-sre-demo/bad-deploy",
  "last_processing_state": "completed"
}
```
