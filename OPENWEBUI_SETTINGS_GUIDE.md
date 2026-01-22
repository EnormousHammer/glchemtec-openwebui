# OpenWebUI Settings Guide - Avoiding Conflicts

## Critical Settings to Configure

### 1. Filter Priorities (Already Set Correctly)

**Current Configuration:**
- **PPT/PDF Vision Filter**: `priority = 0` (runs FIRST - highest priority)
- **Export Filter**: `priority = 10` (runs LATER - lower priority)

**Why This Matters:**
- Vision filter needs to run first to extract images before other processing
- Export filter runs later to catch export requests after AI responds
- ✅ **No action needed** - priorities are already correct

---

### 2. RAG Settings (Potential Conflict)

**Current Settings in `render.yaml`:**
```yaml
PDF_EXTRACT_IMAGES: "true"
RAG_FILE_MAX_SIZE: "100"
RAG_FILE_MAX_COUNT: "10"
ENABLE_RAG_WEB_SEARCH: "false"
```

**Potential Conflict:**
- OpenWebUI's built-in RAG system may try to process PDFs/PPTX files
- This could conflict with our custom vision filter
- RAG extracts text for embeddings, while our filter extracts images for vision

**Recommended Settings:**

**Option A: Disable RAG for PDF/PPTX (Recommended)**
- Keep `PDF_EXTRACT_IMAGES: "true"` (doesn't conflict)
- Keep `ENABLE_RAG_WEB_SEARCH: "false"` (already disabled)
- **In OpenWebUI Admin UI:**
  1. Go to **Settings** → **RAG** (or **Knowledge Base**)
  2. **Disable automatic RAG processing** for:
     - PDF files (`.pdf`)
     - PowerPoint files (`.ppt`, `.pptx`)
  3. Keep RAG enabled for text files (`.txt`, `.md`, etc.)

**Option B: Keep RAG Enabled (Less Recommended)**
- RAG will extract text from PDFs/PPTX
- Our vision filter will extract images
- Both can run, but may cause duplicate processing
- ✅ **Will work, but less efficient**

**Action Required:**
- ✅ Check OpenWebUI Admin → Settings → RAG
- ✅ Disable RAG for PDF/PPTX if you want to avoid duplicate processing
- ✅ Or leave enabled if you want both text embeddings AND image extraction

---

### 3. File Upload Permissions

**Current Setting:**
```yaml
USER_PERMISSIONS_CHAT_FILE_UPLOAD: "true"
```

**Status:** ✅ **Correct** - File uploads must be enabled for filters to work

**Action Required:** ✅ **No action needed**

---

### 4. OpenAI API Configuration

**Current Setting:**
```yaml
OPENAI_API_BASE_URLS: "https://api.openai.com/v1"
```

**Potential Issue:**
- This routes directly to OpenAI
- Our `openai_responses_proxy.py` runs on port 8000
- **These don't conflict** - proxy is separate service

**How It Works:**
- OpenWebUI → Direct to OpenAI (for standard chat)
- Our filters → Process files and add images to requests
- Proxy service → Only used for export functionality

**Action Required:** ✅ **No action needed** - current setup is correct

---

### 5. Filter Enable/Disable Settings

**In OpenWebUI Admin UI:**

1. **Go to:** Admin → Functions (or Settings → Functions)

2. **PPT/PDF Vision Filter:**
   - ✅ **Enabled**: `true` (must be enabled)
   - ✅ **Priority**: `0` (highest - runs first)
   - ✅ **Debug**: `true` (recommended for troubleshooting)
   - **Settings:**
     - `pptx_converter_url`: `https://glc-pptx-converter.onrender.com`
     - `max_pages`: `8` (max PDF pages to process)
     - `dpi`: `150` (image quality)
     - `max_image_width`: `1600`
     - `max_image_height`: `1200`
     - `jpeg_quality`: `85`
     - `max_total_base64_mb`: `5.0`

3. **Export Filter:**
   - ✅ **Enabled**: `true` (if you want export functionality)
   - ✅ **Priority**: `10` (runs after vision filter)
   - ✅ **Debug**: `true` (recommended)
   - **Settings:**
     - `export_service_url`: `http://localhost:8000`

**Action Required:**
- ✅ Verify both filters show as **Enabled** in Admin UI
- ✅ Check filter priorities are correct (0 and 10)

---

### 6. Environment Variables (No Conflicts)

**Current Environment Variables:**
```yaml
RAG_EMBEDDING_MODEL: "text-embedding-3-small"
ENABLE_RAG_WEB_SEARCH: "false"
PDF_EXTRACT_IMAGES: "true"
RAG_FILE_MAX_SIZE: "100"
RAG_FILE_MAX_COUNT: "10"
USER_PERMISSIONS_CHAT_FILE_UPLOAD: "true"
PROXY_DEBUG: "true"
```

**Status:** ✅ **All correct** - no conflicts

**Action Required:** ✅ **No action needed**

---

## Summary: Required Actions

### ✅ Must Check/Configure:

1. **OpenWebUI Admin → Functions:**
   - Verify "PPT/PDF Vision Filter" is **Enabled**
   - Verify "Export Filter" is **Enabled** (if using export)
   - Check priorities: Vision=0, Export=10

2. **OpenWebUI Admin → Settings → RAG:**
   - **Option 1 (Recommended):** Disable RAG for PDF/PPTX files
   - **Option 2:** Keep RAG enabled (will work but less efficient)

3. **Verify File Uploads:**
   - Ensure `USER_PERMISSIONS_CHAT_FILE_UPLOAD: "true"` in environment
   - Users must have permission to upload files

### ✅ Already Correct (No Action Needed):

- Filter priorities (0 and 10)
- File upload permissions
- OpenAI API configuration
- Environment variables
- Proxy service setup

---

## Testing Checklist

After configuring settings, test:

1. ✅ Upload a PDF → Should extract images and send to OpenAI
2. ✅ Upload a PPTX → Should extract images (including from groups)
3. ✅ Upload a DOCX with images → Should extract images
4. ✅ Upload an XLSX with images → Should extract images
5. ✅ Check logs for `[PPT-PDF-VISION]` messages
6. ✅ Check logs for `✅ SUCCESS: OpenAI received and processed the request`

---

## Troubleshooting Conflicts

### Issue: Images Not Extracted

**Check:**
- Filter is enabled in Admin → Functions
- Filter priority is 0 (highest)
- File uploads are enabled
- Check logs for `[PPT-PDF-VISION]` messages

### Issue: Duplicate Processing

**Check:**
- RAG is processing same files as vision filter
- **Solution:** Disable RAG for PDF/PPTX in Settings → RAG

### Issue: Export Not Working

**Check:**
- Export filter is enabled
- Export service URL is correct (`http://localhost:8000`)
- Proxy service is running (check `start.sh`)

---

## Recommended Final Configuration

**Environment Variables (render.yaml):**
```yaml
# Keep these as-is
PDF_EXTRACT_IMAGES: "true"
USER_PERMISSIONS_CHAT_FILE_UPLOAD: "true"
ENABLE_RAG_WEB_SEARCH: "false"
```

**OpenWebUI Admin Settings:**
- **Functions:**
  - PPT/PDF Vision Filter: **Enabled**, Priority: **0**
  - Export Filter: **Enabled**, Priority: **10**
  
- **RAG/Knowledge Base:**
  - **Disable** automatic processing for: `.pdf`, `.ppt`, `.pptx`
  - **Keep enabled** for: `.txt`, `.md`, `.docx` (text only)

This configuration ensures:
- ✅ No conflicts between RAG and vision processing
- ✅ Images are extracted before other processing
- ✅ Export functionality works correctly
- ✅ Optimal performance (no duplicate processing)
