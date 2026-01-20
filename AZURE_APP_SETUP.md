# Azure App Registration Setup for OpenWebUI

## Your Current App Details

- **Client ID**: `e1d3755c-410b-4988-b1e5-676afc13e672`
- **Tenant ID**: `fb807ad4-223e-4e42-97f7-b0029deb0e69`

## Step-by-Step Azure Configuration

### 1. Go to Azure Portal
- Visit: https://portal.azure.com
- Sign in with your Microsoft account

### 2. Find Your App Registration
- Navigate to: **Azure Active Directory** → **App registrations**
- Search for or find your app with Client ID: `e1d3755c-410b-4988-b1e5-676afc13e672`
- Click on it to open

### 3. Get/Create Client Secret

**Option A: If you already have a secret:**
- Go to **Certificates & secrets** (left menu)
- Under **Client secrets**, find an existing secret
- If it's expired, create a new one (see Option B)
- **Copy the VALUE** (not the Secret ID) - you'll only see it once!

**Option B: Create a new secret:**
- Go to **Certificates & secrets** (left menu)
- Click **+ New client secret**
- Description: `OpenWebUI OAuth`
- Expires: Choose duration (24 months recommended)
- Click **Add**
- **IMMEDIATELY copy the VALUE** - it won't show again!
- Save it somewhere safe (we'll add it to credentials.txt)

### 4. Configure Redirect URI

- Go to **Authentication** (left menu)
- Under **Platform configurations**, click **+ Add a platform**
- Select **Web**
- Add this redirect URI:
  ```
  https://glchemtec-openwebui.onrender.com/oauth/microsoft/callback
  ```
  (Replace with your actual Render URL after deployment)
- Click **Configure**

### 5. Set API Permissions

- Go to **API permissions** (left menu)
- Click **+ Add a permission**
- Select **Microsoft Graph**
- Select **Delegated permissions**
- Add these permissions:
  - `openid`
  - `email`
  - `profile`
  - `User.Read`
- Click **Add permissions**
- **Important**: Click **Grant admin consent** (if you're an admin)

### 6. Configure Authentication Settings

- Go to **Authentication** (left menu)
- Under **Implicit grant and hybrid flows**:
  - ✅ ID tokens (used for implicit and hybrid flows)
- Under **Supported account types**:
  - Choose based on your needs:
    - **Single tenant** - Only your organization
    - **Multi-tenant** - Any organization
    - **Multi-tenant + personal** - Any organization + personal Microsoft accounts
- Click **Save**

## What You'll Need for Render

After completing the above, you'll have:

1. ✅ **Client ID**: `e1d3755c-410b-4988-b1e5-676afc13e672` (already have)
2. ✅ **Tenant ID**: `fb807ad4-223e-4e42-97f7-b0029deb0e69` (already have)
3. ⚠️ **Client Secret**: [The VALUE you copied from step 3]

## Next Steps

1. Add the Client Secret to `credentials.txt` (I can help with this)
2. Add `MICROSOFT_CLIENT_SECRET` to Render environment variables
3. Update the redirect URI in Azure once you know your Render URL
4. Test the OAuth flow

## Important Notes

- **Client Secret expires**: Set a reminder to renew it before expiration
- **Redirect URI must match exactly**: Including `https://` and the full path
- **HTTPS required**: Render provides this automatically
- **First deployment**: You may need to update the redirect URI after you get your Render URL

## Troubleshooting

### "Invalid redirect URI" error
- Make sure the redirect URI in Azure matches exactly what's in Render
- Check for trailing slashes
- Verify HTTPS is used

### "Invalid client secret" error
- Secret might be expired - create a new one
- Make sure you copied the VALUE, not the Secret ID
- Check for extra spaces when pasting

### "Insufficient permissions" error
- Grant admin consent in API permissions
- Verify all required permissions are added
