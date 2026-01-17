#!/bin/bash

# Start the OpenAI Responses Proxy in background on port 8000
echo "Starting OpenAI Responses Proxy on port 8000..."
uvicorn openai_responses_proxy:app --host 0.0.0.0 --port 8000 &
PROXY_PID=$!

# Wait for proxy to be ready
sleep 3

# Start OpenWebUI (the base image's default command)
echo "Starting OpenWebUI..."
exec /app/backend/start.sh
