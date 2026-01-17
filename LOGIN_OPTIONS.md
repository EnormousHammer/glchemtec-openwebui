# Login Options - Both Available! ✅

## Current Configuration

Your OpenWebUI is set up to show **BOTH** login options:

1. ✅ **Microsoft OAuth** - "Sign in with Microsoft" button
2. ✅ **OpenWebUI Username/Password** - Traditional login form

## What's Configured

In `render.yaml`:
- ✅ `ENABLE_LOGIN_FORM=true` - Shows username/password login
- ✅ `ENABLE_OAUTH_SIGNUP=true` - Shows Microsoft OAuth button
- ✅ `WEBUI_AUTH=true` - Requires login (no anonymous access)

## What You Need in Render

### For Microsoft OAuth to Work:

Make sure these are set in Render → Environment Variables:

1. **MICROSOFT_CLIENT_ID**
   - Your Azure app Client ID
   - Mark as Secret ✓

2. **MICROSOFT_CLIENT_SECRET** ⚠️ **REQUIRED**
   - Your Azure app Client Secret VALUE
   - Mark as Secret ✓

3. **MICROSOFT_TENANT_ID**
   - Your Azure Tenant ID
   - Mark as Secret ✓

4. **OPENID_PROVIDER_URL**
   - Format: `https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0/.well-known/openid-configuration`
   - Replace `YOUR_TENANT_ID` with your actual tenant ID
   - Not secret

### For OpenWebUI Login to Work:

1. **WEBUI_ADMIN_EMAIL** = `haron@glchemtec.com` (already set)
2. **WEBUI_ADMIN_PASSWORD** = `Alhakimi2016!` (you need to add this in Render)
3. **ENABLE_SIGNUP** = `false` (already set - prevents public signups)

## How Users Will See It

When users visit your OpenWebUI:

```
┌─────────────────────────────────┐
│   GLChemTec OpenWebUI          │
│                                 │
│   [Sign in with Microsoft]     │  ← Microsoft OAuth
│                                 │
│   ─────────── OR ───────────   │
│                                 │
│   Email/Username: [_______]     │  ← OpenWebUI Login
│   Password:      [_______]     │
│                                 │
│   [Login]                       │
└─────────────────────────────────┘
```

## Login Options Explained

### Option 1: Microsoft OAuth
- User clicks "Sign in with Microsoft"
- Redirected to Microsoft login
- After Microsoft login, redirected back
- Account created automatically (if first time)
- Works with any Microsoft account (based on your Azure settings)

### Option 2: OpenWebUI Username/Password
- User enters email/username and password
- Uses the admin account you created:
  - Email: `haron@glchemtec.com`
  - Password: `Alhakimi2016!`
- Or any other accounts you create later

## Current Status Checklist

- [x] `ENABLE_LOGIN_FORM=true` - Username/password enabled
- [x] `ENABLE_OAUTH_SIGNUP=true` - Microsoft OAuth enabled
- [x] `WEBUI_AUTH=true` - Authentication required
- [ ] `MICROSOFT_CLIENT_ID` - Add in Render
- [ ] `MICROSOFT_CLIENT_SECRET` - Add in Render (from Azure)
- [ ] `MICROSOFT_TENANT_ID` - Add in Render
- [ ] `OPENID_PROVIDER_URL` - Add in Render
- [ ] `WEBUI_ADMIN_PASSWORD` - Add in Render

## After Adding All Variables

1. Save all environment variables in Render
2. Redeploy the service
3. Visit your Render URL
4. You should see **BOTH** login options:
   - Microsoft OAuth button at the top
   - Username/password form below

## If You Want Only One Option

### Microsoft Only:
- Set `ENABLE_LOGIN_FORM=false` in Render
- Only Microsoft OAuth will show

### Username/Password Only:
- Remove or don't set Microsoft OAuth variables
- Only username/password form will show

## Next Steps

Since you've added the Render URL to Azure:

1. ✅ Get your Azure credentials:
   - Client ID
   - Client Secret (from Certificates & secrets)
   - Tenant ID

2. ✅ Add all Microsoft variables to Render

3. ✅ Add `WEBUI_ADMIN_PASSWORD` = `Alhakimi2016!` to Render

4. ✅ Add `OPENID_PROVIDER_URL` with your tenant ID

5. ✅ Redeploy

6. ✅ Test both login methods!
