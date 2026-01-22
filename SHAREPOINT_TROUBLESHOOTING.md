# SharePoint Integration - Troubleshooting Guide

## Common Issues and Fixes

### Issue 1: "SharePoint integration not enabled" or "Can't browse SharePoint"

**Symptoms:**
- Error message saying SharePoint isn't configured
- Browser shows "Error loading files"
- API returns 403 or 400 errors

**Fix:**

1. **Check Environment Variables in Render:**
   Go to Render Dashboard → Your Service → Environment → Make sure these are set:
   ```
   ENABLE_SHAREPOINT=true
   SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/YourSite
   SHAREPOINT_FOLDER=Documents
   SHAREPOINT_CLIENT_ID=your_client_id_here
   SHAREPOINT_CLIENT_SECRET=your_client_secret_here
   SHAREPOINT_TENANT_ID=your_tenant_id_here
   ```

2. **Verify Azure AD App Permissions:**
   - Go to Azure Portal → Azure AD → App registrations → Your App
   - Click **API permissions**
   - Make sure you have **APPLICATION permissions** (not delegated):
     - ✅ `Sites.ReadWrite.All` (Application permission)
     - OR `Sites.Selected` with specific site access
   - **IMPORTANT**: Click **Grant admin consent** button
   - Wait a few minutes for permissions to propagate

3. **Check Client Secret:**
   - Go to Azure Portal → Your App → Certificates & secrets
   - Make sure secret is **not expired**
   - Copy the **VALUE** (not Secret ID) - it only shows once!
   - Update `SHAREPOINT_CLIENT_SECRET` in Render

4. **Verify Site URL Format:**
   - Must be: `https://yourcompany.sharepoint.com/sites/SiteName`
   - NOT: `https://yourcompany.sharepoint.com` (missing /sites/...)
   - Check in SharePoint: Site Settings → Site Information → Web Address

5. **Restart Service:**
   - After changing environment variables, restart your Render service
   - Go to Render Dashboard → Your Service → Manual Deploy → Clear build cache & deploy

### Issue 2: "Token request failed" or "Authentication error"

**Symptoms:**
- 401 Unauthorized errors
- "Token request failed" in logs

**Fix:**

1. **Verify Credentials:**
   - Double-check `SHAREPOINT_CLIENT_ID`, `SHAREPOINT_CLIENT_SECRET`, `SHAREPOINT_TENANT_ID`
   - Make sure there are no extra spaces or quotes
   - Client Secret is the **VALUE**, not the Secret ID

2. **Check Azure AD App:**
   - Go to Azure Portal → Your App → Overview
   - Verify Application (client) ID matches `SHAREPOINT_CLIENT_ID`
   - Verify Directory (tenant) ID matches `SHAREPOINT_TENANT_ID`

3. **Check API Permissions:**
   - Must have **APPLICATION permissions** (not delegated)
   - `Sites.ReadWrite.All` or `Sites.Selected`
   - **Admin consent must be granted** (green checkmark)

### Issue 3: "No files found" or Empty file list

**Symptoms:**
- Browser loads but shows "No files found"
- Empty file list

**Fix:**

1. **Check Folder Path:**
   - Verify `SHAREPOINT_FOLDER` matches actual folder name in SharePoint
   - Default is `Documents` (the default document library)
   - If using custom folder, use exact name (case-sensitive)

2. **Check Site Permissions:**
   - Make sure the Azure AD app has access to the SharePoint site
   - If using `Sites.Selected`, you must grant access to specific sites
   - Go to SharePoint Admin Center → Advanced → API access → Grant access

3. **Verify Site URL:**
   - Make sure `SHAREPOINT_SITE_URL` is correct
   - Test by opening the URL in browser (should load SharePoint site)

### Issue 4: Browser iframe not loading

**Symptoms:**
- Chat shows iframe but it's blank
- "Failed to load" in iframe

**Fix:**

1. **Check Proxy URL:**
   - The iframe loads from `/sharepoint-browser`
   - Make sure proxy service is running on same domain
   - If proxy is on different port, update the URL in filter

2. **Check CORS:**
   - Make sure proxy allows requests from OpenWebUI domain
   - Check browser console for CORS errors

3. **Check Service Status:**
   - Verify proxy service is running
   - Check Render logs for errors

## Step-by-Step Setup Verification

### 1. Azure AD App Setup

✅ **App Registration:**
- [ ] Created app in Azure Portal
- [ ] Copied Application (client) ID
- [ ] Copied Directory (tenant) ID
- [ ] Created client secret and copied VALUE

✅ **API Permissions:**
- [ ] Added `Sites.ReadWrite.All` (Application permission)
- [ ] Clicked "Grant admin consent"
- [ ] See green checkmark next to permission

✅ **Authentication:**
- [ ] Redirect URI configured (for OAuth, not needed for SharePoint import)

### 2. Render Environment Variables

✅ **Set in Render Dashboard:**
- [ ] `ENABLE_SHAREPOINT=true`
- [ ] `SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/YourSite`
- [ ] `SHAREPOINT_FOLDER=Documents`
- [ ] `SHAREPOINT_CLIENT_ID=your_client_id`
- [ ] `SHAREPOINT_CLIENT_SECRET=your_client_secret_value`
- [ ] `SHAREPOINT_TENANT_ID=your_tenant_id`

### 3. Test Connection

✅ **Test in Chat:**
1. Type: "Browse SharePoint"
2. Should see iframe with file browser
3. If error, check Render logs for details

✅ **Test API Directly:**
1. Go to: `https://your-app.onrender.com/api/v1/sharepoint/files`
2. Should return JSON with files list
3. If error, check error message for what's missing

## Quick Diagnostic Commands

### Check if SharePoint is enabled:
```bash
# In Render logs, look for:
[SHAREPOINT-IMPORT] SharePoint import filter initialized
```

### Check if credentials are loaded:
```bash
# In Render logs, look for:
[SHAREPOINT-IMPORT] SharePoint credentials not configured
# OR
[SHAREPOINT-IMPORT] Token request failed: ...
```

### Test API endpoint:
```bash
curl https://your-app.onrender.com/api/v1/sharepoint/files
# Should return JSON or error message
```

## Still Not Working?

1. **Check Render Logs:**
   - Go to Render Dashboard → Your Service → Logs
   - Look for `[SHAREPOINT-IMPORT]` messages
   - Copy error messages

2. **Verify Azure AD App:**
   - Make sure app is in same tenant as SharePoint
   - Check that admin consent was granted
   - Wait 5-10 minutes after granting permissions

3. **Test Graph API Directly:**
   - Use Graph Explorer: https://developer.microsoft.com/graph/graph-explorer
   - Sign in and test: `GET /sites/{site-id}/drives`
   - If this works, the issue is with credentials/config

4. **Common Mistakes:**
   - ❌ Using delegated permissions instead of application permissions
   - ❌ Not granting admin consent
   - ❌ Using Secret ID instead of Secret VALUE
   - ❌ Wrong site URL format
   - ❌ Forgetting to restart service after changing env vars

---

**Need Help?** Check Render logs and share the error message - it will tell you exactly what's missing!
