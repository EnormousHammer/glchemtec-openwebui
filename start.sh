#!/bin/bash
# Don't exit on error - we want to see what's happening
# set -e

cd /app

echo "=== Starting Services ===" >&2
echo "Current directory: $(pwd)" >&2
echo "PORT environment variable: ${PORT:-8080}" >&2

echo "" >&2
echo "=== Starting OpenAI Responses Proxy ===" >&2
python3 -m uvicorn openai_responses_proxy:app --host 0.0.0.0 --port 8000 >&2 &
PROXY_PID=$!
echo "Proxy started with PID: $PROXY_PID" >&2

# Wait for proxy to be ready (up to 30 seconds)
for i in {1..30}; do
  if (echo > /dev/tcp/127.0.0.1/8000) >/dev/null 2>&1; then
    echo "✓ Proxy is up on port 8000" >&2
    break
  fi
  echo "Waiting for proxy... ($i/30)" >&2
  sleep 1
done

# Check if proxy process is still alive
if ! kill -0 $PROXY_PID 2>/dev/null; then
  echo "ERROR: Proxy process died!" >&2
  wait $PROXY_PID 2>/dev/null || true
fi

echo "" >&2
echo "=== Starting OpenWebUI ===" >&2
echo "PORT will be: ${PORT:-8080}" >&2
echo "OpenWebUI start script: /app/backend/start.sh" >&2

# Enforce GLChemTec branding assets and custom CSS at runtime (handles persisted volumes)

if [ -f "/app/backend/open_webui/static/branding/GLC_icon.png" ]; then
  cp /app/backend/open_webui/static/branding/GLC_icon.png /app/backend/open_webui/static/favicon.ico 2>/dev/null || true
  cp /app/backend/open_webui/static/branding/GLC_icon.png /app/backend/open_webui/static/favicon.png 2>/dev/null || true
fi
if [ -f "/app/backend/open_webui/static/branding/GLC_Logo.png" ]; then
  cp /app/backend/open_webui/static/branding/GLC_Logo.png /app/backend/open_webui/static/logo.png 2>/dev/null || true
fi

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
