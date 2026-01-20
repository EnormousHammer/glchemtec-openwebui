# Setup Both Login Options - OpenWebUI + Microsoft

## ✅ What's Already Configured

Your `render.yaml` has:
- ✅ `ENABLE_OAUTH_SIGNUP = true` (Microsoft OAuth enabled)
- ✅ `ENABLE_LOGIN_FORM = true` (Username/password login enabled)
- ✅ `WEBUI_AUTH = true` (Authentication required)
- ✅ Microsoft variables configured

## What You Need to Verify in Render

Go to Render Dashboard → Environment Variables and make sure you have:

### For Microsoft OAuth:
1. ✅ `MICROSOFT_CLIENT_ID` = `e1d3755c-410b-4988-b1e5-676afc13e672` (you have this)
2. ✅ `MICROSOFT_CLIENT_SECRET` = (your secret - you have this)
3. ✅ `MICROSOFT_TENANT_ID` = `fb807ad4-223e-4e42-97f7-b0029deb0e69` (you have this)
4. ⚠️ `OPENID_PROVIDER_URL` = `https://login.microsoftonline.com/fb807ad4-223e-4e42-97f7-b0029deb0e69/v2.0/.well-known/openid-configuration`
   - **Check if this is set correctly** (use your actual tenant ID)

### For OpenWebUI Login:
5. ✅ `ENABLE_LOGIN_FORM = true` (should be set)
6. ✅ `ENABLE_PASSWORD_AUTH = true` (add if missing)

### General:
7. ✅ `WEBUI_AUTH = true` (you have this)
8. ✅ `ENABLE_OAUTH_SIGNUP = true` (should be set)

## What Users Will See

When users visit your OpenWebUI, they'll see:

```
┌─────────────────────────────────┐
│   GLChemTec OpenWebUI          │
│                                 │
│   [🔵 Sign in with Microsoft]  │  ← Microsoft OAuth
│                                 │
│   ─────────── OR ───────────   │
│                                 │
│   Email/Username: [_______]     │  ← OpenWebUI Login
│   Password:       [_______]     │
│                                 │
│   [Login]                       │
└─────────────────────────────────┘
```

## If Microsoft Button Doesn't Show

If the "Sign in with Microsoft" button doesn't appear, check:
1. All Microsoft variables are set in Render
2. `OPENID_PROVIDER_URL` uses the correct tenant ID
3. Azure app has the correct redirect URI set

## Test It

1. Log out of your admin account
2. Visit your Render URL
3. You should see BOTH login options
4. Test both:
   - Click "Sign in with Microsoft" → Should redirect to Microsoft
   - Or use username/password → Should log in directly

## Done!

Once both are working, users can choose either login method!
