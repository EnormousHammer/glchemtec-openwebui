# Restore Login Screen with Both Options

## What You Should See

Your login screen should show:
1. **"Sign in with Microsoft"** button (top)
2. **OR divider**
3. **Username/Password form** (below)

## Current Configuration Check

Make sure these are set in Render → Environment Variables:

### Required for Both Login Options:

1. **ENABLE_LOGIN_FORM** = `true` ✅ (enables username/password)
2. **ENABLE_OAUTH_SIGNUP** = `true` ✅ (enables Microsoft OAuth button)
3. **WEBUI_AUTH** = `true` ✅ (requires login)

### For Microsoft OAuth to Show:

4. **MICROSOFT_CLIENT_ID** - Must be set
5. **MICROSOFT_CLIENT_SECRET** - Must be set
6. **MICROSOFT_TENANT_ID** - Must be set
7. **OPENID_PROVIDER_URL** - Must be set

## If You're Only Seeing Signup

If you're seeing a signup form instead of login:

1. **Check if you're logged out:**
   - Clear browser cookies/cache
   - Visit the URL again
   - You should see login screen

2. **Make sure ENABLE_SIGNUP is set correctly:**
   - If `ENABLE_SIGNUP=false` → Only login shows (no signup)
   - If `ENABLE_SIGNUP=true` → Both login and signup show

## Quick Fix Steps

### Step 1: Verify Environment Variables in Render

Go to Render Dashboard → Environment and check:

- [ ] `ENABLE_LOGIN_FORM` = `true`
- [ ] `ENABLE_OAUTH_SIGNUP` = `true`
- [ ] `WEBUI_AUTH` = `true`
- [ ] `MICROSOFT_CLIENT_ID` is set
- [ ] `MICROSOFT_CLIENT_SECRET` is set
- [ ] `MICROSOFT_TENANT_ID` is set
- [ ] `OPENID_PROVIDER_URL` is set

### Step 2: If Microsoft OAuth Button is Missing

The Microsoft button won't show if OAuth variables aren't set. Make sure all Microsoft variables are added.

### Step 3: Clear Browser Cache

1. Clear cookies for your Render URL
2. Or use incognito/private mode
3. Visit the URL again

### Step 4: Check Current Screen

**What screen are you seeing?**
- Signup form only?
- Login form only?
- Both login and signup?
- Microsoft button missing?

## Expected Login Screen Layout

```
┌─────────────────────────────────────┐
│   GLChemTec OpenWebUI               │
│                                     │
│   [🔵 Sign in with Microsoft]      │  ← Microsoft OAuth
│                                     │
│   ─────────── OR ───────────        │
│                                     │
│   Email/Username: [________]        │  ← Username/Password
│   Password:       [________]        │
│                                     │
│   [Login]  [Sign Up]                │
└─────────────────────────────────────┘
```

## If You Want to Disable Signup

If you only want login (no signup option):

1. Set `ENABLE_SIGNUP=false` in Render
2. Redeploy
3. Users will only see login options (Microsoft or username/password)

## Troubleshooting

### Only seeing signup?
- Set `ENABLE_SIGNUP=false` to hide signup
- Or just sign up once, then you'll see login next time

### Microsoft button not showing?
- Check all Microsoft OAuth variables are set
- Verify `ENABLE_OAUTH_SIGNUP=true`
- Check Render logs for OAuth errors

### Only seeing username/password?
- Check `ENABLE_OAUTH_SIGNUP=true`
- Verify Microsoft variables are set
- OAuth button needs all Microsoft variables to show

## What to Do Now

1. **Check Render Environment Variables** - Make sure all are set
2. **Clear browser cache** - Visit URL in incognito mode
3. **Check what you're seeing** - Describe the screen
4. **Redeploy if needed** - After changing variables

Tell me what screen you're seeing and I can help fix it!
