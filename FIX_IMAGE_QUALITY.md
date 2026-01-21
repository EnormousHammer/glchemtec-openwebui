# Fix Image Quality for Better Readability

## Current Problem

**Your images are TOO compressed** - making them unreadable for:
- Small text in slides
- Chemical structures
- NMR spectra
- Charts and graphs
- Fine details

## Current Settings (TOO LOW)

```python
dpi: 72              # Low - text becomes blurry
max_width: 800px     # Small - details lost
max_height: 600px    # Small - content cramped
jpeg_quality: 40     # VERY LOW (0-100) - heavy compression artifacts
```

## How OpenAI Receives Images

1. **We compress images** (current: quality=40, 800x600, 72 DPI)
2. **Convert to base64** data URL: `data:image/jpeg;base64,{data}`
3. **Send to OpenAI Responses API** as `input_image` with the data URL
4. **OpenAI uses them AS-IS** - they don't resize or recompress
5. **If we send low quality, OpenAI can't read it well**

## The Fix

Increase quality settings for better readability:

```python
dpi: 150             # Higher - clearer text
max_width: 1600px    # Larger - more detail
max_height: 1200px   # Larger - more content visible
jpeg_quality: 85     # HIGH quality - minimal compression
max_total_base64_mb: 5.0  # Allow larger total size
```

## Impact

**Current (Low Quality):**
- File size: ~50-100KB per image
- Text readability: ❌ Poor (blurry)
- Details: ❌ Lost
- Spectra: ❌ Unclear peaks

**Recommended (High Quality):**
- File size: ~200-400KB per image
- Text readability: ✅ Good (clear)
- Details: ✅ Preserved
- Spectra: ✅ Clear peaks

## Recommendation

**Increase quality** - the file size increase is worth it for readability, especially for technical/chemical documents.
