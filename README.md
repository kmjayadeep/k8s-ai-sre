# k8s-ai-sre

> AI-assisted Kubernetes incident investigation with guarded remediation. 🤖🛡️

`k8s-ai-sre` helps you move from alert to safe action faster:

1. **detect** an issue (via HTTP or Alertmanager webhook)
2. **investigate** with real cluster evidence (`kubectl` reads + Prometheus)
3. **propose** actionable remediation steps
4. **approve/reject** each action explicitly (Telegram or HTTP API)
5. **execute** only guarded mutations with namespace constraints

![k8s-ai-sre architecture](assets/readme-architecture.svg)

## Why this?

When something breaks in-cluster, this gives you one loop:

```
alert → investigate → propose → approve → execute
```

Designed to be practical first, not magic-first.

## Quick start 🚀

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure

Required environment variables:

```bash
export MODEL_NAME=openai/gpt-oss-20b
export MODEL_API_KEY=your-api-key
export MODEL_PROVIDER=groq                    # or openai, anthropic, etc.
export MODEL_BASE_URL=https://api.groq.com/openai/v1
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo
```

### 3. Create demo failure

```bash
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f examples/kind-bad-deploy.yaml
```

### 4. Run service

```bash
uv run main.py
```

### 5. Trigger investigation

```bash
curl -X POST http://127.0.0.1:8080/investigate \
  -H 'Content-Type: application/json' \
  -d '{"kind":"deployment","namespace":"ai-sre-demo","name":"bad-deploy"}'
```

Then open the UI: http://127.0.0.1:8080/

## Telegram approval (optional) 💬

```bash
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
export TELEGRAM_ALLOWED_CHAT_IDS=...
```

Commands: `/incident`, `/status`, `/approve`, `/reject`

## Guardrails 🔒

- Write actions require explicit approval before execution
- Namespace allow-list via `WRITE_ALLOWED_NAMESPACES`
- Actions perform `kubectl auth can-i` checks (fail-closed)
- Supported actions: `delete-pod`, `rollout-restart`, `scale`, `rollout-undo`

## Deployment ☸️

See [docs/deployment.md](docs/deployment.md) for Kubernetes deployment.

```bash
kubectl create namespace ai-sre-system --dry-run=client -o yaml | kubectl apply -f -
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=MODEL_NAME="$MODEL_NAME" \
  --from-literal=MODEL_PROVIDER="$MODEL_PROVIDER" \
  --from-literal=MODEL_BASE_URL="$MODEL_BASE_URL" \
  --from-literal=MODEL_API_KEY="$MODEL_API_KEY" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="$WRITE_ALLOWED_NAMESPACES" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k deploy
```

Image: `ghcr.io/kmjayadeep/k8s-ai-sre:main`

## Testing 🧪

```bash
uv run python -m unittest discover -s tests
```

See [TESTING.md](TESTING.md) for detailed test scenarios.

## Docs

- [Quick Start Guide](docs/quickstart.md)
- [Deployment Guide](docs/deployment.md)
- [Testing Guide](TESTING.md)
- [API Reference](docs/api.md) - for detailed API docs
- [docs/](docs/) - full documentation

## Code map 🧭

| File | Purpose |
|------|---------|
| `main.py` | Service entrypoint |
| `app/http.py` | API routes + incident inspector UI |
| `app/investigate.py` | Investigation orchestration |
| `app/tools/k8s.py` | Kubernetes + Prometheus reads |
| `app/tools/actions.py` | Guarded mutating actions |
| `app/telegram.py` | Telegram polling and command handling |
| `app/stores/` | Incident/action store abstraction |
| `model_factory.py` | Model provider wiring |
