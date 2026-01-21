# How to Get Render Logs Automatically

## Option 1: Use the Python Script (Recommended)

I've created `get_render_logs.py` that automatically fetches and analyzes your Render logs.

### Setup:

1. **Get your Render API key:**
   - Go to: https://dashboard.render.com/account/api-keys
   - Click "New API Key"
   - Copy the key

2. **Set the API key:**
   ```bash
   # Windows PowerShell
   $env:RENDER_API_KEY="your_api_key_here"
   
   # Or add to your environment permanently
   ```

3. **Run the script:**
   ```bash
   python get_render_logs.py
   ```

4. **The script will:**
   - Find your service automatically
   - Fetch the last 200 log entries
   - Analyze for errors, warnings, and issues
   - Categorize problems (import errors, filter issues, etc.)
   - Save logs to `render_logs.json`
   - Give you recommendations

### What it finds:

- ✅ **Import errors** (missing packages)
- ✅ **Filter errors** (syntax/import issues in filters)
- ✅ **Proxy issues** (openai_responses_proxy problems)
- ✅ **Database errors** (connection/permission issues)
- ✅ **Startup errors** (anything preventing OpenWebUI from starting)
- ✅ **All errors and warnings** with context

## Option 2: Manual Log Retrieval

If you prefer to get logs manually:

1. **Via Render Dashboard:**
   - Go to: https://dashboard.render.com
   - Click your service: `glchemtec-openwebui`
   - Click "Logs" tab
   - Copy the error messages

2. **Via Render CLI:**
   ```bash
   # Install Render CLI
   npm install -g render-cli
   
   # Login
   render login
   
   # Get logs
   render logs glchemtec-openwebui --tail
   ```

## Option 3: Check Logs in Real-Time

The script can be modified to watch logs in real-time. Just add a loop:

```python
import time
while True:
    logs = get_logs(api_key, service_id)
    # Analyze and print
    time.sleep(10)  # Check every 10 seconds
```

## What to Look For

The script automatically finds these common issues:

### Critical Errors:
- `ModuleNotFoundError` - Missing Python package
- `ImportError` - Can't import a module
- `SyntaxError` - Code has syntax errors
- `ValueError(ERROR_MESSAGES.ENV_VAR_NOT_FOUND)` - Missing environment variable
- `Permission denied` - File/directory permission issues

### Filter-Specific:
- `[EXPORT-FILTER] ERROR` - Export filter issues
- `[PPT-PDF-VISION] ERROR` - Vision filter issues
- Any traceback mentioning filter files

### Service Issues:
- `Proxy is up` - Should see this if proxy starts
- `Starting OpenWebUI...` - Should see this if OpenWebUI starts
- `Uvicorn running on` - Should see this when server is ready

## Quick Test

Run this to test if the script works:

```bash
python get_render_logs.py
```

If it works, you'll see:
- Service found
- Logs retrieved
- Analysis with specific errors highlighted

## Troubleshooting the Script

**Error: "Service not found"**
- Update `SERVICE_NAME` in the script to match your Render service name exactly

**Error: "Unauthorized"**
- Check your API key is correct
- Make sure API key has read permissions

**Error: "No logs retrieved"**
- Service might not be running
- Check service status in Render dashboard
- Try increasing the `limit` parameter

## Next Steps After Getting Logs

Once you have the logs:

1. **Share the error messages** with me
2. **Look for the first error** in the log (usually the root cause)
3. **Check the recommendations** the script provides
4. **Fix the specific issue** identified

The script makes it much easier to find what's actually breaking!
