#!/bin/bash
# Don't exit on error - we want to see what's happening
# set -e

cd /app

echo "=== Starting Services ==="
echo "Current directory: $(pwd)"
echo "PORT environment variable: ${PORT:-8080}"

echo ""
echo "=== Starting OpenAI Responses Proxy ==="
python3 -m uvicorn openai_responses_proxy:app --host 0.0.0.0 --port 8000 &

# Wait for proxy to be ready (up to 30 seconds)
for i in {1..30}; do
  if (echo > /dev/tcp/127.0.0.1/8000) >/dev/null 2>&1; then
    echo "✓ Proxy is up on port 8000"
    break
  fi
  echo "Waiting for proxy... ($i/30)"
  sleep 1
done

echo ""
echo "=== Starting OpenWebUI ==="
echo "PORT will be: ${PORT:-8080}"
echo "OpenWebUI start script: /app/backend/start.sh"

# Check if start script exists
if [ ! -f "/app/backend/start.sh" ]; then
    echo "ERROR: /app/backend/start.sh not found!"
    echo "Listing /app/backend contents:"
    ls -la /app/backend/ || true
    exit 1
fi

# Ensure PORT is available to OpenWebUI
export PORT=${PORT:-8080}

echo "Executing OpenWebUI start script..."
exec /app/backend/start.sh
