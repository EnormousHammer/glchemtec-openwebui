# Next Steps - Your OpenWebUI is Live! 🎉

## ✅ What's Working Now

- OpenWebUI is deployed and running on Render
- Database is set up
- Basic configuration is complete

## 🎯 What to Do Next

### Step 1: Get Your Render URL

1. Go to Render Dashboard → Your Service
2. Copy your service URL (e.g., `https://glchemtec-openwebui.onrender.com`)
3. **Save this URL** - you'll need it for Azure setup

### Step 2: Set Up Azure App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **+ New registration**

**App Details:**
- **Name**: `GLChemTec OpenWebUI`
- **Supported account types**: Choose based on who should access
- Click **Register**

**After Registration:**
- Copy **Application (client) ID** → This is your `MICROSOFT_CLIENT_ID`
- Copy **Directory (tenant) ID** → This is your `MICROSOFT_TENANT_ID`

### Step 3: Create Client Secret

1. In your Azure app → **Certificates & secrets**
2. Click **+ New client secret**
3. Description: `OpenWebUI OAuth`
4. Expires: 24 months (or your preference)
5. Click **Add**
6. **IMMEDIATELY copy the VALUE** (you won't see it again!)
7. This is your `MICROSOFT_CLIENT_SECRET`

### Step 4: Configure Redirect URI in Azure

1. In Azure app → **Authentication**
2. Click **+ Add a platform** → Select **Web**
3. Add redirect URI:
   ```
   https://YOUR-RENDER-URL.onrender.com/oauth/microsoft/callback
   ```
   (Use your actual Render URL from Step 1)
4. Click **Configure**

### Step 5: Set API Permissions

1. In Azure app → **API permissions**
2. Click **+ Add a permission**
3. Select **Microsoft Graph** → **Delegated permissions**
4. Add these:
   - ✅ `openid`
   - ✅ `email`
   - ✅ `profile`
   - ✅ `User.Read`
5. Click **Add permissions**
6. Click **Grant admin consent** (if you're an admin)

### Step 6: Add Variables to Render

Go to Render Dashboard → Your Service → **Environment** tab

Add these variables:

1. **MICROSOFT_CLIENT_ID**
   - Value: [From Step 2]
   - Mark as **Secret** ✓

2. **MICROSOFT_CLIENT_SECRET**
   - Value: [From Step 3]
   - Mark as **Secret** ✓

3. **MICROSOFT_TENANT_ID**
   - Value: [From Step 2]
   - Mark as **Secret** ✓

4. **OPENID_PROVIDER_URL**
   - Value: `https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0/.well-known/openid-configuration`
   - Replace `YOUR_TENANT_ID` with your actual tenant ID
   - Not secret

### Step 7: Enable Authentication

Make sure these are set in Render:
- ✅ `WEBUI_AUTH` = `true` (should already be set)
- ✅ `ENABLE_OAUTH_SIGNUP` = `true` (should already be set)
- ✅ `ENABLE_LOGIN_FORM` = `true` (should already be set)

### Step 8: Redeploy

1. Save all environment variables in Render
2. Trigger a manual redeploy (or wait for auto-deploy)
3. Wait for deployment to complete

### Step 9: Test It!

1. Visit your Render URL
2. You should see a login page
3. Click **"Sign in with Microsoft"**
4. Log in with your Microsoft account
5. You should be redirected back and logged in!

## 🎉 Success Checklist

- [ ] Render URL obtained
- [ ] Azure app created
- [ ] Client ID, Tenant ID, Client Secret saved
- [ ] Redirect URI configured in Azure
- [ ] API permissions granted
- [ ] All variables added to Render
- [ ] Service redeployed
- [ ] Can log in with Microsoft
- [ ] Can access OpenWebUI interface

## 🔧 Optional: Update credentials.txt

Once you have all the Azure info, I can update `credentials.txt` with the new values for your records.

## 🚨 Troubleshooting

### Can't log in with Microsoft?
- Check redirect URI matches exactly in Azure
- Verify all environment variables are set
- Check Render logs for errors

### Still seeing public access?
- Verify `WEBUI_AUTH=true` is set
- Clear browser cache
- Try incognito mode

### OAuth button not showing?
- Check `ENABLE_OAUTH_SIGNUP=true`
- Verify Microsoft variables are set
- Check logs for configuration errors

## 📝 What You Can Do Now

While setting up Azure, you can:
- ✅ Test OpenWebUI features (if auth is disabled)
- ✅ Upload files and test processing
- ✅ Try the chat interface
- ✅ Explore the UI

Once Azure is configured, authentication will be required!

---

**Need help with any step? Let me know!**
