# Local Testing Guide & LibreOffice Evaluation

## Quick Answer: Is LibreOffice Best?

**Yes, LibreOffice is the best option for your use case** because:

1. **Free & Open Source** - No licensing costs
2. **Preserves Visual Fidelity** - Critical for vision analysis (charts, spectra, diagrams)
3. **Headless Operation** - Works in Docker/server environments
4. **Already in Production** - Your Dockerfile already installs it
5. **Cross-Platform** - Works on Linux (Docker), Windows, macOS

### Alternatives Considered:

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **LibreOffice** ✅ | Free, preserves formatting, headless | Requires installation | **BEST CHOICE** |
| Microsoft Office COM | Native Windows, perfect formatting | Requires Office license, Windows-only, no headless | ❌ Not suitable |
| python-pptx + reportlab | Pure Python, no external deps | Loses visual formatting (bad for vision) | ❌ Loses charts/diagrams |
| Cloud APIs (Google/Office365) | No local install | Costs money, requires auth, slower | ❌ Overkill |
| unoconv | Lightweight wrapper | Still needs LibreOffice | ❌ Same dependency |

## Local Testing Options

### Option 1: Test with PDF Files Directly (Easiest)

**Skip PPT conversion entirely** - test the PDF→images pipeline:

```bash
# Convert your PPTX to PDF manually (or use online converter)
# Then test with the PDF file
python test_ppt_vision_local.py
```

The script automatically detects if a PDF version exists and uses it.

**Pros:**
- No LibreOffice needed
- Tests the core functionality (PDF→images→OpenAI format)
- Fast iteration

**Cons:**
- Doesn't test PPT→PDF conversion
- Need to manually convert PPTX first

### Option 2: Fix LibreOffice Locally

**Reinstall LibreOffice properly:**

1. Download from: https://www.libreoffice.org/download/
2. Install normally (not via winget if it's causing issues)
3. Verify: `soffice --version` works
4. Run test: `python test_ppt_vision_local.py`

**Pros:**
- Tests full pipeline
- Matches production environment

**Cons:**
- Requires installation
- Can have Windows-specific issues

### Option 3: Use Docker Locally

**Run the same Docker container locally:**

```bash
# Build the Docker image
docker build -t glchemtec-openwebui .

# Run with your test file mounted
docker run -v "C:\APPLICATIONS MADE BY ME\WINDOWS\glchemtec_openwebui\test_files:/test" glchemtec-openwebui
```

**Pros:**
- Exact production environment
- LibreOffice already working
- Tests everything

**Cons:**
- Requires Docker
- Slower iteration

### Option 4: Mock/Test Mode (Development Only)

Add a test mode that skips conversion:

```python
# In ppt_pdf_vision_filter.py
if os.environ.get("TEST_MODE") == "skip_conversion":
    # Skip to PDF→images step
    pass
```

**Pros:**
- Fast development cycle
- No dependencies

**Cons:**
- Doesn't test real conversion
- Only for development

## Recommended Testing Strategy

1. **For Development/Quick Tests:** Use Option 1 (test with PDFs directly)
2. **For Full Integration Tests:** Use Option 3 (Docker locally)
3. **For Production:** Already working in Render with Docker

## Current Status

- ✅ **Production (Render):** LibreOffice installed in Docker - should work
- ⚠️ **Local Windows:** LibreOffice corrupted - use PDF testing or Docker
- ✅ **Code:** Windows path detection added - will work once LibreOffice is fixed

## Next Steps

1. **Immediate:** Test with PDF files using `test_ppt_vision_local.py`
2. **Short-term:** Fix LibreOffice locally OR use Docker for full testing
3. **Production:** Deploy and verify in Render (LibreOffice already there)
