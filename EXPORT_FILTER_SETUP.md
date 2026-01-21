# Export Filter Setup Guide

## Overview

The `export_filter.py` allows users to export conversations to Word (.docx) or PDF files by simply asking the AI (e.g., "export this to PDF" or "create a Word file").

## How It Works

1. **User Request**: User types something like "export this to PDF" or "create a Word file"
2. **Filter Detection**: The filter detects the export request in the `inlet` method (before AI responds)
3. **File Generation**: Filter generates the file using the proxy service at `http://localhost:8000`
4. **File Saving**: File is saved to `/app/backend/data/uploads/` directory
5. **Download Link**: Filter provides a download link in the AI's response

## Prerequisites

### 1. Required Services

- **OpenWebUI** must be running
- **OpenAI Responses Proxy** must be running on port 8000 (handled by `start.sh`)
  - The proxy provides `/v1/report/pdf` and `/v1/report/docx` endpoints

### 2. Required Python Packages

All packages should already be in `requirements.txt`:
- `pydantic` - For filter configuration
- `requests` - For calling the export service
- `python-docx` - For Word file generation (in proxy)
- `reportlab` - For PDF generation (in proxy)

### 3. File Locations

The filter must be placed in one of these locations (both are set in Dockerfile):
- `/app/backend/filters/export_filter.py`
- `/app/backend/custom/filters/export_filter.py`

OpenWebUI auto-loads filters from these directories.

## Configuration

### Environment Variables

Add these to your Render dashboard or `.env` file:

```bash
# Export service URL (default: http://localhost:8000)
EXPORT_SERVICE_URL=http://localhost:8000

# Upload directory (default: /app/backend/data/uploads)
UPLOAD_DIR=/app/backend/data/uploads
```

**Note**: These are optional - the filter uses sensible defaults if not set.

### Filter Settings (via OpenWebUI Admin)

Once the filter is loaded, you can configure it in OpenWebUI:

1. Go to **Admin** → **Functions** (or **Settings** → **Functions**)
2. Find "Document Export Filter"
3. Configure:
   - **Enabled**: `true` (enable/disable the filter)
   - **Debug**: `true` (enable detailed logging)
   - **Priority**: `10` (higher = runs later in pipeline)
   - **Export Service URL**: `http://localhost:8000` (proxy service)

## OpenWebUI Setup Steps

### Step 1: Verify Filter is Loaded

1. Start OpenWebUI
2. Check logs for: `[EXPORT-FILTER] Export filter initialized`
3. If you don't see this, the filter isn't loading

### Step 2: Enable the Filter

The filter should auto-load, but verify:

1. Go to **Admin** → **Functions**
2. Look for "Document Export Filter" in the list
3. If it's there, click to configure
4. Ensure **Enabled** is set to `true`

**Note**: If the filter doesn't appear in the UI, it may still work - OpenWebUI auto-loads filters from the filesystem.

### Step 3: Test the Filter

1. Start a conversation
2. Type: "export this conversation to PDF" or "create a Word file"
3. The AI should respond with a download link
4. Check logs for `[EXPORT-FILTER]` messages

## Troubleshooting

### Filter Not Working

**Check 1: Filter is loaded**
- Look for `[EXPORT-FILTER] Export filter initialized` in logs
- If missing, check file is in correct location

**Check 2: Export service is running**
- Verify proxy is running: `curl http://localhost:8000/health` (or check logs)
- Look for "Starting OpenAI Responses Proxy on port 8000..." in startup logs

**Check 3: Export request detection**
- Check logs for `[EXPORT-FILTER] Export request detected in inlet: PDF`
- If not appearing, the pattern matching might not be catching your request
- Try: "export to pdf", "create word file", "make pdf document"

**Check 4: File generation**
- Check logs for `[EXPORT-FILTER] Export file generated and saved in inlet`
- If missing, the proxy service might be failing
- Check proxy logs for errors

### Common Issues

**Issue: "Filter never attached a single thing"**
- **Cause**: OpenWebUI doesn't support adding files to assistant messages after generation
- **Solution**: The filter now generates files in `inlet` and provides download links in message text
- **Workaround**: Download links are embedded in the AI's response text

**Issue: "500 Internal Error" on startup**
- **Cause**: Filter might have syntax/import errors
- **Solution**: Run `python test_export_filter.py` to validate
- **Temporary fix**: Comment out filter in Dockerfile to test if it's the cause

**Issue: "Export service not found"**
- **Cause**: Proxy service not running or wrong URL
- **Solution**: 
  - Check `start.sh` is starting the proxy
  - Verify `EXPORT_SERVICE_URL` environment variable
  - Check proxy logs for startup errors

**Issue: "File saved but no download link"**
- **Cause**: Filter might not be enhancing the assistant message
- **Solution**: Check `outlet` method is running (look for `[EXPORT-FILTER] Outlet called` in logs)

## Testing Locally

Before deploying, test locally:

```bash
# 1. Test filter syntax
python test_export_filter.py

# 2. Test filter instantiation
python -c "import export_filter; f = export_filter.Filter(); print('OK')"

# 3. Test export detection
python -c "import export_filter; f = export_filter.Filter(); print(f._detect_export_request('export to pdf'))"
```

## Expected Behavior

### When User Says "Export to PDF":

1. **Inlet** (before AI responds):
   - Filter detects: `[EXPORT-FILTER] Export request detected in inlet: PDF`
   - Generates file: `[EXPORT-FILTER] Export file generated and saved in inlet: /app/backend/data/uploads/export_20250121_123456.pdf`
   - Modifies user message to tell AI about the file

2. **AI Response**:
   - AI responds normally, but knows about the file
   - AI should mention the file and provide download link

3. **Outlet** (after AI responds):
   - Filter enhances: `[EXPORT-FILTER] Enhanced assistant message with download link for export_20250121_123456.pdf`
   - Adds download link if AI didn't include it

### Log Messages to Look For

```
[EXPORT-FILTER] Export filter initialized
[EXPORT-FILTER] Inlet called
[EXPORT-FILTER] Export request detected in inlet: PDF
[EXPORT-FILTER] Requesting export from: http://localhost:8000/v1/report/pdf
[EXPORT-FILTER] Export file generated and saved in inlet: /app/backend/data/uploads/export_20250121_123456.pdf (45234 bytes)
[EXPORT-FILTER] Outlet called
[EXPORT-FILTER] Enhanced assistant message with download link for export_20250121_123456.pdf
```

## No Conflicts with Other Filters

The export filter:
- ✅ Uses priority 10 (runs after most filters)
- ✅ Only processes when export request is detected
- ✅ Doesn't modify files or other filter data
- ✅ Safe to run alongside `ppt_pdf_vision_filter.py`

## File Size Limits

- **Small files (<5MB)**: Uses data URL for direct download
- **Large files (≥5MB)**: Provides file path (user must access via file system)

## Security Notes

- Files are saved to `/app/backend/data/uploads/` (same as user uploads)
- Files use timestamped names to avoid conflicts
- No authentication required to generate files (relies on OpenWebUI auth)
- Consider adding file cleanup for old exports if needed
