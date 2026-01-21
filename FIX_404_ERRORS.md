# Fix 404 Errors - Port Configuration Issue

## The Problem

All requests are returning 404 errors. This is typically caused by:

1. **Port Mismatch**: Render uses a dynamic `PORT` environment variable (usually 10000), but OpenWebUI might be listening on 8080
2. **OpenWebUI not starting**: The app might not be starting at all
3. **Static files not accessible**: Static files directory might have permission issues

## The Fix

OpenWebUI needs to listen on the `PORT` environment variable that Render provides, not hardcoded 8080.

### Solution: Update start.sh

The issue is that OpenWebUI's start script might be hardcoded to port 8080, but Render provides a `PORT` env var.

We need to ensure OpenWebUI uses the PORT env var. However, since we're using the official OpenWebUI Docker image, it should already handle this.

### Check These:

1. **Is OpenWebUI actually starting?**
   - Check Render logs for "Starting OpenWebUI..." or "Uvicorn running on..."
   - If you don't see these, OpenWebUI isn't starting

2. **What port is it listening on?**
   - Look for "Uvicorn running on http://0.0.0.0:XXXX"
   - Should match Render's PORT (usually 10000)

3. **Is the proxy interfering?**
   - The proxy runs on port 8000
   - Make sure it's not blocking OpenWebUI

## Quick Fix to Try

Update `start.sh` to ensure PORT is respected:

```bash
#!/bin/bash
set -e

cd /app

echo "Starting OpenAI Responses Proxy on port 8000..."
python3 -m uvicorn openai_responses_proxy:app --host 0.0.0.0 --port 8000 &

# Wait for proxy to be ready
for i in {1..30}; do
  if (echo > /dev/tcp/127.0.0.1/8000) >/dev/null 2>&1; then
    echo "Proxy is up on port 8000"
    break
  fi
  echo "Waiting for proxy... ($i/30)"
  sleep 1
done

echo "Starting OpenWebUI..."
echo "PORT environment variable: ${PORT:-8080}"

# OpenWebUI should automatically use PORT env var
# But if not, we might need to pass it explicitly
exec /app/backend/start.sh
```

## Alternative: Check if OpenWebUI is Running

The 404s might mean OpenWebUI isn't starting at all. Check Render logs for:

- Python errors
- Import errors
- Missing environment variables
- Database connection errors

## Most Likely Cause

Based on the 404 errors, **OpenWebUI is probably not starting at all**. The container is running, but the application isn't.

Check Render logs for the actual startup error - that will tell us what's wrong.
