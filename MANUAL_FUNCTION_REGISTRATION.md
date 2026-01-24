# How to Manually Add SharePoint Import in Admin UI

Since OpenWebUI requires manual function registration, here's how to add SharePoint Import:

## Step 1: Get the Filter File Path

The filter file is located at:
```
/app/backend/filters/sharepoint_import_filter.py
```

Or in your Dockerfile, it's copied to:
- `/app/backend/filters/sharepoint_import_filter.py`
- `/app/backend/custom/filters/sharepoint_import_filter.py`

## Step 2: Add in Admin UI

1. **Go to Admin → Functions** (or Settings → Functions)
2. **Click "Add Function"** or "New Function" button
3. **Choose one of these options:**

### Option A: Add from File Path
- **Function Type**: Select "Filter" or "Custom Function"
- **File Path**: `/app/backend/filters/sharepoint_import_filter.py`
- **Name**: `SharePoint Import Filter`
- **Enabled**: `true`

### Option B: Copy File Contents
If the UI requires you to paste code:
1. Copy the entire contents of `sharepoint_import_filter.py`
2. Paste into the function editor
3. Save

### Option C: Import from URL/File
Some OpenWebUI versions allow importing from:
- File path in container
- GitHub URL
- Direct code paste

## Step 3: Configure Settings

After adding, configure these settings:

```json
{
  "enabled": true,
  "enable_sharepoint": true,
  "sharepoint_site_url": "https://glchemtec.sharepoint.com/sites/YourSite",
  "sharepoint_folder": "Documents",
  "debug": true,
  "priority": 5
}
```

## Step 4: Set Environment Variables

Make sure these are set in Render:
- `ENABLE_SHAREPOINT=true`
- `SHAREPOINT_SITE_URL=...`
- `SHAREPOINT_CLIENT_ID=...`
- `SHAREPOINT_CLIENT_SECRET=...`
- `SHAREPOINT_TENANT_ID=...`

## Alternative: Convert to Pipe/Function Format

If the Filter format doesn't work, we can convert it to a `Pipe` format that OpenWebUI definitely recognizes. This would require:
- Changing `class Filter:` to `class Pipe:`
- Adding `pipes()` method
- Adjusting the structure

**Would you like me to convert it to Pipe format?**

## Quick Test

After adding:
1. Check logs for: `[SHAREPOINT-IMPORT] SharePoint import filter initialized`
2. Type "browse sharepoint" in chat
3. Check logs for: `[SHAREPOINT-IMPORT] Inlet called`

---

**Note**: If you can share a screenshot of the "Add Function" UI, I can give more specific instructions based on your OpenWebUI version.
