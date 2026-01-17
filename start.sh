#!/bin/bash
set -e

echo "Starting OpenAI Responses Proxy on port 8000..."
uvicorn openai_responses_proxy:app --host 0.0.0.0 --port 8000 &

# Wait for proxy to be ready (up to 30 seconds)
for i in {1..30}; do
  if (echo > /dev/tcp/127.0.0.1/8000) >/dev/null 2>&1; then
    echo "Proxy is up on port 8000"
    break
  fi
  echo "Waiting for proxy... ($i/30)"
  sleep 1
done

echo "Starting OpenWebUI..."
exec /app/backend/start.sh
