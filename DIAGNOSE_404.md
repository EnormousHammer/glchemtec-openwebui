# Diagnosing 404 Errors

## What 404 Errors Mean

404 = "Not Found" - This means:
- ✅ The server/container IS running (otherwise you'd get connection refused)
- ❌ The application (OpenWebUI) is NOT running or NOT listening on the correct port
- ❌ Routes/static files are not being served

## Most Likely Causes

### 1. OpenWebUI Not Starting (90% likely)

The container runs, but OpenWebUI crashes during startup. Check Render logs for:

**Look for these startup messages:**
- `Starting OpenWebUI...` ✅ Should see this
- `Uvicorn running on http://0.0.0.0:XXXX` ✅ Should see this
- `Application startup complete` ✅ Should see this

**If you DON'T see these, OpenWebUI isn't starting!**

**Common startup failures:**
- Missing environment variables
- Import errors in filters
- Database connection errors
- Permission errors

### 2. Port Mismatch (10% likely)

OpenWebUI might be listening on 8080, but Render expects it on PORT (usually 10000).

**Check logs for:**
- `Uvicorn running on http://0.0.0.0:8080` ❌ Wrong port
- `Uvicorn running on http://0.0.0.0:10000` ✅ Correct port

The official OpenWebUI Docker image should handle PORT automatically, but verify.

### 3. Static Files Not Accessible

If OpenWebUI starts but static files (CSS, JS) return 404:
- Permission issues on `/app/backend/open_webui/static`
- Static files not copied during build

## How to Diagnose

### Step 1: Check Render Logs

Go to Render Dashboard → Logs and look for:

1. **Startup sequence:**
   ```
   Starting OpenAI Responses Proxy on port 8000...
   Proxy is up on port 8000
   Starting OpenWebUI...
   PORT environment variable: 10000
   ```

2. **OpenWebUI startup:**
   ```
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:10000
   ```

3. **Any errors:**
   - `Traceback`
   - `ERROR`
   - `Exception`
   - `ModuleNotFoundError`
   - `ImportError`

### Step 2: Check Service Health

The health check path is `/health`. Try accessing:
- `https://glchemtec-openwebui.onrender.com/health`

If this returns 404, OpenWebUI definitely isn't running.

### Step 3: Check What's Actually Running

The container might be running, but only the proxy might be up. Check logs for:
- `Proxy is up on port 8000` ✅
- But no OpenWebUI startup messages ❌

## Quick Fixes to Try

### Fix 1: Ensure PORT is Set

I've updated `start.sh` to log the PORT. After redeploy, check logs to see what PORT is being used.

### Fix 2: Check if Filters Are Breaking Startup

The export filter is disabled, but `ppt_pdf_vision_filter.py` might have issues.

**Temporarily disable all filters:**
```dockerfile
# Comment out filter copies
# COPY ppt_pdf_vision_filter.py /app/backend/filters/ppt_pdf_vision_filter.py
# COPY ppt_pdf_vision_filter.py /app/backend/custom/filters/ppt_pdf_vision_filter.py
```

### Fix 3: Check Environment Variables

Missing required env vars can prevent startup. Verify in Render:
- `OPENAI_API_KEY` ✅
- `WEBUI_SECRET_KEY` ✅
- `WEBUI_URL` ✅

## What to Share

Please share from Render logs:
1. **Last 50-100 lines** of logs
2. **Any error messages** (especially tracebacks)
3. **Startup messages** (or lack thereof)
4. **What you see** when accessing the service URL

This will tell us exactly what's wrong!
