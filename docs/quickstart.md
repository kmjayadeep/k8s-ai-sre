# Quick Start

## 1. Install dependencies

```bash
uv sync
```

## 2. Configure model credentials

Minimum:

```bash
export PORTKEY_API_KEY=...
```

Optional overrides:

```bash
export MODEL_NAME=openai/gpt-oss-20b
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.portkey.ai/v1
export MODEL_API_KEY=...
```

`MODEL_API_KEY` overrides `PORTKEY_API_KEY` when both are set.

## 3. Create demo scenario

```bash
kubectl create namespace ai-sre-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f examples/kind-bad-deploy.yaml
```

## 4. Start the service

```bash
uv run main.py
```

## 5. Trigger investigation

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

## Expected response fields

Investigation creation endpoints return normalized incident payloads including:

- `incident_id`
- `source`
- `answer`
- `action_ids`
- `proposed_actions`
