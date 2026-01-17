# Quick Fix for Current Errors

## The Two Errors:

1. **Permission denied on `.webui_secret_key`** - Fixed in Dockerfile
2. **ENV_VAR_NOT_FOUND** - Missing required environment variable

## Immediate Fix Steps:

### Step 1: Add WEBUI_SECRET_KEY to Render

1. Go to Render Dashboard → Your Service → Environment tab
2. Add this variable:
   - **Key**: `WEBUI_SECRET_KEY`
   - **Value**: Generate a random string (see below)
   - **Mark as Secret** ✓

**Generate Secret Key:**
- Use: `openssl rand -hex 32` (if you have openssl)
- Or use an online generator: https://randomkeygen.com/
- Or use this Python: `python -c "import secrets; print(secrets.token_hex(32))"`
- Copy a long random string (64+ characters)

### Step 2: Add Required Variables (Minimum to Start)

Add these to Render Environment Variables:

**Critical (Must Have):**
- ✅ `WEBUI_SECRET_KEY` = [your generated secret]
- ✅ `OPENAI_API_KEY` = [your OpenAI key]

**For OAuth (Add when Azure is ready):**
- `MICROSOFT_CLIENT_ID` = [your client ID]
- `MICROSOFT_CLIENT_SECRET` = [your client secret]
- `MICROSOFT_TENANT_ID` = [your tenant ID]
- `OPENID_PROVIDER_URL` = `https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0/.well-known/openid-configuration`

**Optional (Can add later):**
- `WEBUI_AUTH` = `true` (only if OAuth is configured)
- `ENABLE_OAUTH_SIGNUP` = `true`
- `ENABLE_LOGIN_FORM` = `true`

### Step 3: Temporarily Disable Auth (If OAuth Not Ready)

If you haven't set up Azure yet, **temporarily** set:
- `WEBUI_AUTH` = `false` (or remove it)

This lets OpenWebUI start without OAuth configured. You can enable it later.

### Step 4: Redeploy

After adding `WEBUI_SECRET_KEY`:
1. Save all environment variables
2. Trigger manual redeploy
3. Check logs

## What Changed:

✅ Dockerfile now handles permission issues
✅ `WEBUI_SECRET_KEY` must be set manually (not auto-generated)
✅ You can start without OAuth, then add it later

## After It Starts:

Once OpenWebUI is running:
1. Get your Render URL
2. Set up Azure app with that URL
3. Add OAuth variables
4. Set `WEBUI_AUTH=true`
5. Redeploy
