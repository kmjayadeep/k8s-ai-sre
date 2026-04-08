# Portkey Integration

This guide shows how to configure `k8s-ai-sre` to route model requests through [Portkey](https://portkey.ai/).

Portkey acts as a gateway, providing tracing, retries, load balancing, and unified access across multiple LLM providers.

## Setup

### 1. Get your Portkey API key

Sign up at [portkey.ai](https://portkey.ai/) and create an API key.

### 2. Configure environment

```bash
export MODEL_API_KEY=pk-your-portkey-api-key
export MODEL_PROVIDER=portkey
export MODEL_BASE_URL=https://api.portkey.ai/v1
export MODEL_NAME=openai/gpt-oss-20b     # or any model supported by your Portkey config
export WRITE_ALLOWED_NAMESPACES=ai-sre-demo
```

### 3. Optional: Configure target provider in Portkey

You can specify the actual provider in your Portkey dashboard or via virtual keys:

```bash
# Use a specific provider via virtual key
export MODEL_API_KEY=pk-your-portkey-virtual-key
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.portkey.ai/v1
export MODEL_NAME=llama-3.1-70b
```

## Using Portkey Tracing

Portkey can trace your investigation requests. Configure the trace endpoint in your Portkey dashboard or use a custom base URL with trace headers.

## Provider Examples

Portkey supports many providers. Here are common configurations:

```bash
# OpenAI via Portkey
export MODEL_API_KEY=pk-your-portkey-key
export MODEL_PROVIDER=openai
export MODEL_BASE_URL=https://api.portkey.ai/v1
export MODEL_NAME=gpt-4o

# Anthropic via Portkey
export MODEL_API_KEY=pk-your-portkey-key
export MODEL_PROVIDER=anthropic
export MODEL_BASE_URL=https://api.portkey.ai/v1
export MODEL_NAME=claude-sonnet-4-20250514

# Groq via Portkey
export MODEL_API_KEY=pk-your-portkey-key
export MODEL_PROVIDER=groq
export MODEL_BASE_URL=https://api.portkey.ai/v1
export MODEL_NAME=llama-3.1-70b-versatile
```

## Kubernetes Deployment

```bash
kubectl -n ai-sre-system create secret generic k8s-ai-sre-env \
  --from-literal=MODEL_API_KEY="$MODEL_API_KEY" \
  --from-literal=MODEL_PROVIDER="$MODEL_PROVIDER" \
  --from-literal=MODEL_BASE_URL="$MODEL_BASE_URL" \
  --from-literal=MODEL_NAME="$MODEL_NAME" \
  --from-literal=WRITE_ALLOWED_NAMESPACES="$WRITE_ALLOWED_NAMESPACES" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Notes

- Portkey uses your Portkey API key as `MODEL_API_KEY`
- The `MODEL_PROVIDER` value can be anything; it's used for tracing/metadata in Portkey
- Set `MODEL_BASE_URL` to `https://api.portkey.ai/v1`
- `MODEL_NAME` should match a model available in your Portkey configuration
