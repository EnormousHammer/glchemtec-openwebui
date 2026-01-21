# Image Quality Analysis - How OpenAI Receives Images

## Current Settings (TOO AGGRESSIVE)

Looking at `ppt_pdf_vision_filter.py`:

```python
dpi: int = 72                    # Low DPI - may lose detail
max_image_width: int = 800       # Small width
max_image_height: int = 600      # Small height  
jpeg_quality: int = 40           # VERY LOW quality (0-100 scale)
```

## How Images Are Sent to OpenAI

1. **PDF Processing:**
   - PDF pages converted to images at **72 DPI**
   - Images resized to max **800x600 pixels**
   - Saved as JPEG with **quality=40** (very compressed)
   - Converted to base64
   - Sent as: `data:image/jpeg;base64,{base64_data}`

2. **PPTX Images:**
   - Extracted directly from PPTX (no compression by us)
   - Sent as: `data:image/png;base64,{base64_data}` or `data:image/jpeg;base64,{base64_data}`

3. **OpenAI Receives:**
   - Via Responses API as `input_image` with the data URL
   - OpenAI does NOT compress/resize further - they use what we send
   - But if we send low-quality images, OpenAI can't read them well

## The Problem

**JPEG quality=40 is TOO LOW** for:
- ❌ Small text in slides (becomes blurry)
- ❌ Chemical structures (lines become fuzzy)
- ❌ NMR spectra (peaks become unclear)
- ❌ Charts/graphs (axis labels unreadable)
- ❌ Fine details (lost in compression)

**800x600 is TOO SMALL** for:
- ❌ Complex slides with lots of content
- ❌ Detailed diagrams
- ❌ High-resolution content

**72 DPI is TOO LOW** for:
- ❌ Text-heavy slides
- ❌ Documents with fine print

## Recommended Settings

For **readable text and clear images**:

```python
dpi: int = 150                    # Higher DPI for text clarity
max_image_width: int = 1600      # Larger width
max_image_height: int = 1200     # Larger height
jpeg_quality: int = 85           # High quality (85-95 is good)
max_total_base64_mb: float = 5.0 # Allow more total size
```

## Does OpenAI Shrink Them?

**NO** - OpenAI uses the images exactly as we send them. They don't:
- Resize them
- Recompress them
- Modify the data URLs

**BUT** - If we send low-quality images, OpenAI can't magically make them better. The model sees what we send.

## Impact on Readability

With current settings (quality=40, 800x600, 72 DPI):
- ✅ General content: Usually readable
- ❌ Small text: Often blurry/unreadable
- ❌ Fine details: Lost in compression
- ❌ Chemical structures: Lines may be fuzzy
- ❌ Spectra: Peaks may be unclear

With recommended settings (quality=85, 1600x1200, 150 DPI):
- ✅ General content: Very clear
- ✅ Small text: Readable
- ✅ Fine details: Preserved
- ✅ Chemical structures: Clear lines
- ✅ Spectra: Clear peaks

## Trade-offs

**Current (Low Quality):**
- ✅ Smaller file size
- ✅ Faster upload
- ❌ Poor readability for details

**Recommended (High Quality):**
- ✅ Better readability
- ✅ Preserves details
- ❌ Larger file size (but still manageable)
- ❌ Slightly slower upload

## Recommendation

**Increase quality settings** for better readability, especially for:
- Chemical documents
- Technical slides
- Spectra analysis
- Detailed diagrams

The file size increase is worth it for readability.
