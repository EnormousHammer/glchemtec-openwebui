# Create New Azure App Registration for OpenWebUI

## Step-by-Step: Create Azure App from Scratch

### 1. Go to Azure Portal
- Visit: https://portal.azure.com
- Sign in with your Microsoft account

### 2. Navigate to App Registrations
- Click on **Azure Active Directory** (or search for it)
- In the left menu, click **App registrations**
- Click **+ New registration** (top left)

### 3. Register Your Application

**Name:**
```
GLChemTec OpenWebUI
```
(or any name you prefer)

**Supported account types:**
- Choose based on who should access:
  - **Accounts in this organizational directory only** - Just your organization
  - **Accounts in any organizational directory** - Any organization
  - **Accounts in any organizational directory and personal Microsoft accounts** - Anyone with Microsoft account

**Redirect URI (optional for now):**
- Platform: **Web**
- URI: Leave blank for now (we'll add it after deployment)
- Or add: `https://glchemtec-openwebui.onrender.com/oauth/microsoft/callback`
  (We'll update this with your actual Render URL later)

Click **Register**

### 4. Save Your App Details

After registration, you'll see the **Overview** page. **SAVE THESE NOW:**

- **Application (client) ID**: Copy this - this is your `MICROSOFT_CLIENT_ID`
- **Directory (tenant) ID**: Copy this - this is your `MICROSOFT_TENANT_ID`

**Example:**
```
Application (client) ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Directory (tenant) ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 5. Create Client Secret

- Click **Certificates & secrets** (left menu)
- Under **Client secrets**, click **+ New client secret**
- **Description**: `OpenWebUI OAuth Secret`
- **Expires**: Choose **24 months** (or your preference)
- Click **Add**

**⚠️ IMPORTANT: Copy the VALUE immediately!**
- You'll see a **Value** field - this is your `MICROSOFT_CLIENT_SECRET`
- **Copy it NOW** - you won't be able to see it again!
- Save it somewhere safe

### 6. Configure Redirect URI

- Click **Authentication** (left menu)
- Under **Platform configurations**, click **+ Add a platform**
- Select **Web**
- Add redirect URI:
  ```
  https://glchemtec-openwebui.onrender.com/oauth/microsoft/callback
  ```
  (Update this with your actual Render URL after deployment)
- Click **Configure**

### 7. Set API Permissions

- Click **API permissions** (left menu)
- Click **+ Add a permission**
- Select **Microsoft Graph**
- Select **Delegated permissions**
- Search and add these permissions:
  - ✅ `openid` (OpenID Connect sign-in permissions)
  - ✅ `email` (View users' email address)
  - ✅ `profile` (View users' basic profile)
  - ✅ `User.Read` (Sign in and read user profile)
- Click **Add permissions**

**Grant Admin Consent:**
- Click **Grant admin consent for [Your Organization]**
- Click **Yes** to confirm
- This allows all users in your organization to use the app

### 8. Configure Authentication Settings

- Go back to **Authentication** (left menu)
- Under **Implicit grant and hybrid flows**:
  - ✅ Check **ID tokens** (used for implicit and hybrid flows)
- Under **Advanced settings**:
  - **Allow public client flows**: **No** (default is fine)
- Click **Save**

## What You'll Have After Setup

You'll have 3 pieces of information:

1. **MICROSOFT_CLIENT_ID** = Application (client) ID
2. **MICROSOFT_TENANT_ID** = Directory (tenant) ID  
3. **MICROSOFT_CLIENT_SECRET** = The Value from the client secret

## Next Steps

1. **Save all 3 values** - especially the Client Secret (can't retrieve it later)
2. **Update credentials.txt** with the new values
3. **Add to Render** environment variables
4. **Update redirect URI** in Azure after you get your Render URL

## Important Notes

- **Client Secret expires**: Set a calendar reminder to renew before expiration
- **Redirect URI must match exactly**: Including `https://` and full path
- **HTTPS required**: Render provides this automatically
- **First user becomes admin**: The first person to log in via OAuth becomes admin

## After Deployment

Once your Render service is live:

1. Get your Render URL (e.g., `https://glchemtec-openwebui.onrender.com`)
2. Go back to Azure → Your app → Authentication
3. Update the redirect URI to: `https://YOUR-ACTUAL-URL.onrender.com/oauth/microsoft/callback`
4. Save

## Troubleshooting

### Can't find App Registrations?
- Make sure you're in **Azure Active Directory** (not just Azure Portal home)
- You need appropriate permissions (usually admin or app registration creator role)

### Client Secret not showing?
- You can only see the VALUE once when it's created
- If you lost it, create a new one and delete the old one

### Redirect URI errors?
- Must match exactly (case-sensitive, no trailing slashes)
- Must use HTTPS
- Must include the full path: `/oauth/microsoft/callback`
