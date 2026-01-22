# Filters vs Functions - Quick Reference

## ⚠️ ALWAYS CHECK THIS FIRST!

When adding new features, determine if it's a **Filter** or **Function**:

### Filters (Auto-Load, No Registration)
- ✅ **Auto-load** from `/app/backend/filters/` directory
- ✅ **No manual registration** needed
- ✅ **Just add to Dockerfile** - that's it!
- ✅ **Appear in Admin → Functions** for configuration, but work automatically

**Examples in this project:**
- `ppt_pdf_vision_filter.py` - Auto-loads ✅
- `export_filter.py` - Auto-loads ✅
- `sharepoint_import_filter.py` - Auto-loads ✅

**How to verify:**
- Check logs for initialization message
- Look for `[FILTER-NAME] Filter initialized` in startup logs

### Functions/Pipes (Need Registration)
- ❌ **Must be registered** in Admin UI
- ❌ **Must implement `pipes()` method**
- ❌ **More complex setup**

**Example:**
- `ppt_pdf_vision_function.py` - This is a Pipe/Function (different from filter)

## How to Tell the Difference

**Filter:**
```python
class Filter:
    class Valves(BaseModel):
        ...
    def inlet(self, body, __user__):
        ...
    def outlet(self, body, __user__):
        ...
```

**Function/Pipe:**
```python
class Pipe:
    def pipes(self):
        ...
    def pipe(self, body):
        ...
```

## For SharePoint Import

✅ **It's a FILTER** - No registration needed!
- Already in Dockerfile
- Auto-loads on startup
- Just set environment variables
- Check logs to verify it loaded

## Quick Checklist

When adding a new feature, ask:

1. **Is it a Filter or Function?**
   - Filter = Auto-loads, no registration ✅
   - Function = Needs registration ❌

2. **If Filter:**
   - ✅ Add to Dockerfile (copy to `/app/backend/filters/`)
   - ✅ Check logs for initialization
   - ✅ Configure in Admin → Functions (optional, for settings)

3. **If Function:**
   - ❌ Must register in Admin UI
   - ❌ Must implement `pipes()` method
   - ❌ More setup required

---

**Remember:** Filters = Easy, auto-load. Functions = More work, need registration.
