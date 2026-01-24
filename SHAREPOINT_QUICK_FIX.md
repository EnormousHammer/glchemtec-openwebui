# SharePoint Filter Not Working - Quick Fix

## The Problem

When you type "browse sharepoint", OpenAI responds instead of the filter intercepting it.

## Why This Happens

The filter needs to be **enabled** and **detect your message** BEFORE it reaches OpenAI.

## Quick Checklist

### 1. Environment Variables (REQUIRED)

Make sure these are set in Render:

```bash
ENABLE_SHAREPOINT=true
SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/YourSite
SHAREPOINT_FOLDER=Documents
SHAREPOINT_CLIENT_ID=your_client_id
SHAREPOINT_CLIENT_SECRET=your_client_secret
SHAREPOINT_TENANT_ID=your_tenant_id
```

**⚠️ CRITICAL:** `ENABLE_SHAREPOINT=true` must be set, or the filter will skip all requests!

### 2. Check Filter is Loading

After redeploying, check Render logs for:

```
[SHAREPOINT-IMPORT] SharePoint import filter initialized
```

If you DON'T see this, the filter isn't loading.

### 3. Check Filter is Running

When you type "browse sharepoint", check logs for:

```
[SHAREPOINT-IMPORT] Inlet called
```

If you see "Filter disabled or SharePoint not enabled, skipping", then:
- `ENABLE_SHAREPOINT` is not set to `true`
- Or the filter's `enabled` flag is false

### 4. Try These Exact Phrases

The filter detects these patterns:
- ✅ "browse sharepoint"
- ✅ "import from sharepoint"
- ✅ "list sharepoint files"
- ✅ "show sharepoint files"
- ✅ "load file.pdf from sharepoint"

Try: **"browse sharepoint"** (exact phrase)

## What to Do

### Step 1: Verify Environment Variables

1. Go to Render Dashboard
2. Go to your service → Environment
3. Check ALL these are set:
   - `ENABLE_SHAREPOINT=true` ⚠️ **MUST BE TRUE**
   - `SHAREPOINT_SITE_URL=...`
   - `SHAREPOINT_CLIENT_ID=...`
   - `SHAREPOINT_CLIENT_SECRET=...`
   - `SHAREPOINT_TENANT_ID=...`

### Step 2: Redeploy

After setting environment variables:
1. Click "Manual Deploy" in Render
2. Wait for deployment to complete
3. Check logs for filter initialization

### Step 3: Test

1. Open OpenWebUI chat
2. Type: **"browse sharepoint"**
3. Check Render logs immediately after sending

You should see:
```
[SHAREPOINT-IMPORT] Inlet called
[SHAREPOINT-IMPORT] SharePoint import request detected: browse sharepoint
```

If you see:
```
[SHAREPOINT-IMPORT] Filter disabled or SharePoint not enabled, skipping
```

Then `ENABLE_SHAREPOINT` is not set correctly.

## Common Issues

### Issue 1: Filter Not Loading

**Symptom:** No `[SHAREPOINT-IMPORT]` messages in logs at all

**Fix:**
- Check Dockerfile has the filter copied
- Check filter file exists in container
- Restart service

### Issue 2: Filter Disabled

**Symptom:** Logs show "Filter disabled or SharePoint not enabled, skipping"

**Fix:**
- Set `ENABLE_SHAREPOINT=true` in environment variables
- Redeploy

### Issue 3: Pattern Not Detected

**Symptom:** Filter runs but doesn't detect "browse sharepoint"

**Fix:**
- Try exact phrase: "browse sharepoint" (lowercase)
- Or try: "import from sharepoint"
- Check logs for what text was received

### Issue 4: Credentials Missing

**Symptom:** Filter detects request but fails to connect

**Fix:**
- Verify all SharePoint credentials are set
- Check Azure AD app permissions
- See `SHAREPOINT_TROUBLESHOOTING.md`

## Debug Steps

1. **Check if filter loads:**
   ```bash
   # In Render logs, search for:
   [SHAREPOINT-IMPORT] SharePoint import filter initialized
   ```

2. **Check if filter runs:**
   ```bash
   # After typing "browse sharepoint", search for:
   [SHAREPOINT-IMPORT] Inlet called
   ```

3. **Check if request detected:**
   ```bash
   # Should see:
   [SHAREPOINT-IMPORT] SharePoint import request detected: browse sharepoint
   ```

4. **Check if enabled:**
   ```bash
   # Should NOT see:
   [SHAREPOINT-IMPORT] Filter disabled or SharePoint not enabled, skipping
   ```

## Still Not Working?

1. Share the exact log messages you see
2. Confirm all environment variables are set
3. Check if other filters (like export_filter) are working
4. Verify the filter file is in the Dockerfile

---

**TL;DR:** Set `ENABLE_SHAREPOINT=true` and redeploy. Check logs to verify it's loading and running.
