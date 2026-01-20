# Exact Environment Variables You Need in Render

## What You Currently Have (from your screenshot):
✅ DEFAULT_USER_ROLE
✅ ENABLE_SIGNUP  
✅ MICROSOFT_CLIENT_ID
✅ MICROSOFT_CLIENT_SECRET
✅ MICROSOFT_TENANT_ID
✅ OPENAI_API_KEY
✅ OPENID_PROVIDER_URL
✅ WEBUI_NAME
✅ WEBUI_SECRET_KEY

## What's MISSING (causing the permission error):

### Option 1: Auto-Create Admin Account (Recommended)

Add these 3 variables to Render:

1. **WEBUI_ADMIN_EMAIL**
   - Key: `WEBUI_ADMIN_EMAIL`
   - Value: `haron@glchemtec.ca` (or your email)
   - NOT a secret

2. **WEBUI_ADMIN_PASSWORD** ⚠️ **REQUIRED**
   - Key: `WEBUI_ADMIN_PASSWORD`
   - Value: `Alhakimi2016!`
   - Mark as **Secret** ✓

3. **WEBUI_ADMIN_NAME** (Optional)
   - Key: `WEBUI_ADMIN_NAME`
   - Value: `haron alhakimi`
   - NOT a secret

**How this works:**
- OpenWebUI will automatically create the admin account on startup
- You can then log in with the email and password
- No manual signup needed

### Option 2: Allow Manual Signup (If database is empty)

If you want to create the account manually through the web interface:

1. **WEBUI_AUTH**
   - Key: `WEBUI_AUTH`
   - Value: `false` (temporarily, to allow signup)
   - NOT a secret

2. Make sure **ENABLE_SIGNUP** is set to `true` (you already have this)

**Then:**
- Visit your Render URL
- Create account manually
- First user becomes admin automatically

## The Problem:

The permission error happens because:
- Either `WEBUI_AUTH=true` is blocking access (but you don't have this set, so that's not it)
- OR the database already has some data/configuration that's blocking new account creation
- OR you need `WEBUI_ADMIN_PASSWORD` for auto-creation to work

## What To Do Right Now:

**Add these 3 variables to Render:**

1. Click "+ Add Environment Variable" in Render
2. Add:
   - `WEBUI_ADMIN_EMAIL` = `haron@glchemtec.ca`
   - `WEBUI_ADMIN_PASSWORD` = `Alhakimi2016!` (mark as Secret)
   - `WEBUI_ADMIN_NAME` = `haron alhakimi` (optional)
3. Save
4. Redeploy

After redeploy, the admin account will be created automatically and you can log in!
