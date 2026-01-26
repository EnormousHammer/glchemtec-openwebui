# COMPLETE SETUP GUIDE - Everything You Need

## 🚨 CRITICAL: What Must Start First

### 1. Startup Order (in start.sh)
```
1. OpenAI Responses Proxy (port 8000) - MUST START FIRST
2. OpenWebUI (port 8080) - Starts after proxy
3. Route registration scripts (background)
```

### 2. Required Services Running
- ✅ **Proxy on port 8000** - Handles exports and file processing
- ✅ **OpenWebUI on port 8080** - Main application
- ✅ **Route registration** - Makes `/v1/export/*` accessible

---

## 📋 OpenWebUI Functions Settings

### Location: Admin → Functions (or Settings → Functions)

### Filter 1: PPT/PDF Vision Filter
**File:** `/app/backend/filters/ppt_pdf_filter.py`

**Settings:**
```json
{
  "enabled": true,
  "priority": 0,
  "debug": true,
  "dpi": 300,
  "max_pages": 20,
  "output_format": "jpeg",
  "jpeg_quality": 85,
  "max_total_image_mb": 30.0,
  "libreoffice_base_timeout": 15,
  "libreoffice_per_slide_timeout": 1,
  "max_timeout": 60,
  "max_processing_time": 120,
  "extract_text": true,
  "extract_embedded_images": true,
  "convert_emf_wmf": true
}
```

**What it does:**
- Extracts text from PPTX
- Converts PPTX → PDF → Images
- Extracts embedded images
- Converts EMF/WMF to PNG

---

### Filter 2: Export Filter
**File:** `/app/backend/filters/export_filter.py`

**Settings:**
```json
{
  "enabled": true,
  "priority": 10,
  "debug": true,
  "export_service_url": "http://localhost:8000",
  "public_base_url": "https://glchemtec-openwebui.onrender.com",
  "company_name": "GLChemTec",
  "company_logo_path": "/app/backend/open_webui/static/branding/GLC_Logo.png",
  "primary_color": "#1d2b3a",
  "secondary_color": "#e6eef5",
  "enable_sharepoint": false
}
```

**What it does:**
- Detects "export to PDF" or "export to Word" requests
- Creates PDF/DOCX files
- Provides download links

---

## 🔧 Backend Requirements

### 1. Files That Must Exist

**In Dockerfile (already there):**
```
/app/openai_responses_proxy.py          # Proxy service
/app/backend/filters/ppt_pdf_filter.py  # PPT processing
/app/backend/filters/export_filter.py   # Export functionality
/app/backend/export_route_handler.py    # Route registration
/app/register_export_routes.py         # Route registration script
/app/backend/backend_startup_hook.py    # Route registration (backup)
/app/start.sh                           # Startup script
```

### 2. Environment Variables (render.yaml)

**Required:**
```yaml
# Public URL for download links
WEBUI_URL: https://glchemtec-openwebui.onrender.com

# Proxy settings
OPENAI_API_BASE_URLS: "http://localhost:8000/v1"

# Export service
EXPORT_SERVICE_URL: http://localhost:8000
```

**Optional but recommended:**
```yaml
PUBLIC_URL: https://glchemtec-openwebui.onrender.com
RENDER_EXTERNAL_URL: https://glchemtec-openwebui.onrender.com
```

### 3. System Dependencies (in Dockerfile)

**Already installed:**
- LibreOffice (for PPT→PDF conversion)
- poppler-utils (for PDF→images)
- ImageMagick (for EMF/WMF conversion)
- Python packages (from requirements.txt)

---

## 🚀 Startup Sequence

### What Happens When Service Starts:

1. **start.sh runs:**
   ```bash
   # Step 1: Start proxy on port 8000
   python3 -m uvicorn openai_responses_proxy:app --host 0.0.0.0 --port 8000 &
   
   # Step 2: Wait for proxy to be ready
   # (checks port 8000 is listening)
   
   # Step 3: Start OpenWebUI on port 8080
   exec /app/backend/start.sh
   
   # Step 4: Register export routes (background)
   python3 /app/register_export_routes.py &
   ```

2. **OpenWebUI starts:**
   - Loads filters from `/app/backend/filters/`
   - Filters auto-initialize
   - Routes are registered

3. **Route registration:**
   - `register_export_routes.py` tries to find OpenWebUI's app
   - Registers `/v1/export/*` → `localhost:8000`
   - Retries up to 60 times (2 minutes)

---

## ✅ Verification Checklist

### Check 1: Proxy is Running
```bash
# In logs, look for:
"=== Starting OpenAI Responses Proxy ==="
"Proxy started with PID: X"
"✓ Proxy is up on port 8000"
```

### Check 2: Filters Loaded
```bash
# In logs, look for:
"[PPT-PDF-VISION] INLET - PPT/PDF Vision Filter"
"[EXPORT-FILTER] Export filter initialized"
```

### Check 3: Routes Registered
```bash
# In logs, look for:
"[EXPORT-ROUTES] ✅ Successfully registered /v1/export/* routes"
"[EXPORT-PROXY] ✅ Added proxy routes: /v1/export/* → localhost:8000"
```

### Check 4: Test Export
1. Upload a PPT file
2. Ask: "export this to PDF"
3. Check logs for:
   - `[EXPORT-FILTER] Export request detected`
   - `[PROXY] Export file created: ...`
   - `[EXPORT-FILTER] ✅ Added download link`

---

## 🐛 Common Issues

### Issue 1: PPT Extraction Skipped Everything
**Cause:** Time check too strict
**Fix:** Changed from 60% to 40% threshold (already fixed)

### Issue 2: Export Doesn't Work
**Cause:** Routes not registered or headers not preserved
**Fix:** 
- Check `register_export_routes.py` logs
- Verify `Content-Disposition` header in logs
- Check `WEBUI_URL` is set

### Issue 3: Spanish Language
**Cause:** Model/system prompt issue (not related to filters)
**Fix:** Check system prompt or model settings

---

## 📝 What Each Component Does

### openai_responses_proxy.py
- Runs on port 8000
- Handles `/v1/export/create` (creates files)
- Handles `/v1/export/download/{file_id}` (serves files)
- Stores files in memory (expires after 1 hour)

### ppt_pdf_filter.py
- Processes PPT/PDF files
- Extracts text, converts to images
- Adds images to chat for vision analysis

### export_filter.py
- Detects export requests
- Calls proxy to create files
- Adds download links to responses

### register_export_routes.py
- Registers `/v1/export/*` routes with OpenWebUI
- Proxies requests to `localhost:8000`
- Preserves headers (especially Content-Disposition)

---

## 🎯 Quick Fix for Current Issues

### Fix 1: PPT Skipping Everything
**Problem:** Time check at 60% is too strict
**Solution:** Already changed to 40% - will try harder

### Fix 2: Export Not Working
**Problem:** Headers or routes not working
**Solution:** 
- Added better header preservation
- Added logging to track headers
- Both markdown and HTML download links

### Fix 3: Spanish Language
**Problem:** Not a filter issue - model/system prompt
**Solution:** Check OpenWebUI system prompt settings

---

## 📞 If Still Not Working

1. **Check logs for:**
   - Filter initialization messages
   - Route registration messages
   - Export creation messages
   - Download request messages

2. **Verify:**
   - Proxy is running (port 8000)
   - OpenWebUI is running (port 8080)
   - Routes are registered (check logs)
   - Environment variables are set

3. **Test manually:**
   ```bash
   # Test proxy directly
   curl http://localhost:8000/v1/export/create
   
   # Test route through OpenWebUI
   curl https://glchemtec-openwebui.onrender.com/v1/export/download/test
   ```
