# Debug 500 Internal Server Error

## Current Status
- Export filter is temporarily disabled in Dockerfile
- Still getting 500 error
- Need to find the actual error in logs

## Steps to Debug

### Step 1: Check Render Logs for Actual Error

Go to **Render Dashboard** → **Your Service** → **Logs** tab

Look for:
- **Python tracebacks** (lines starting with `Traceback`)
- **Error messages** (lines with `ERROR`, `Exception`, `Failed`)
- **Import errors** (lines with `ModuleNotFoundError`, `ImportError`)
- **Startup errors** (errors during container startup)

**Copy the FULL error message** - this will tell us what's actually breaking.

### Step 2: Check if OpenWebUI is Starting

Look for these in logs:
- `Starting OpenWebUI...`
- `Uvicorn running on...`
- `Application startup complete`

If you DON'T see these, OpenWebUI isn't starting at all.

### Step 3: Check Proxy Service

Look for:
- `Starting OpenAI Responses Proxy on port 8000...`
- `Proxy is up on port 8000`

If proxy fails, it might crash the whole container.

### Step 4: Common Causes of 500 Error

1. **Missing Environment Variable**
   - Check for `ValueError(ERROR_MESSAGES.ENV_VAR_NOT_FOUND)`
   - Missing `WEBUI_SECRET_KEY` or `OPENAI_API_KEY`

2. **Import Error in Filter**
   - Check for `ModuleNotFoundError` or `ImportError`
   - Could be from `ppt_pdf_vision_filter.py` or other filters

3. **Database Error**
   - Check for database connection errors
   - Permission errors on database files

4. **Proxy Service Crash**
   - If `openai_responses_proxy.py` has an error, it might crash
   - Check for Python errors related to the proxy

5. **Missing Python Package**
   - Check for `ModuleNotFoundError: No module named 'X'`
   - Could be missing from `requirements.txt`

## What to Share

Please share:
1. **The actual error message** from Render logs (the traceback/exception)
2. **Last 50-100 lines** of logs when the 500 error occurs
3. **Any startup messages** you see (or don't see)

## Quick Test: Disable All Filters

If you want to test if filters are the issue, temporarily comment out ALL filters in Dockerfile:

```dockerfile
# Temporarily disable all filters
# COPY ppt_pdf_vision_filter.py /app/backend/filters/ppt_pdf_vision_filter.py
# COPY ppt_pdf_vision_filter.py /app/backend/custom/filters/ppt_pdf_vision_filter.py
# COPY export_filter.py /app/backend/filters/export_filter.py
# COPY export_filter.py /app/backend/custom/filters/export_filter.py
```

Then redeploy and see if 500 error goes away.

## Most Likely Issues

Based on your setup, the 500 error is probably from:

1. **Missing `pydantic` in requirements.txt** (if export filter was trying to load)
   - But we disabled it, so this shouldn't be it

2. **Proxy service failing to start**
   - Check if `openai_responses_proxy.py` has errors
   - Check if port 8000 is already in use

3. **OpenWebUI itself crashing**
   - Missing environment variable
   - Database issue
   - Permission issue

**The actual error in the logs will tell us exactly what's wrong.**
