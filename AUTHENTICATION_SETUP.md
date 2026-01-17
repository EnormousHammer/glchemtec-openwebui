# Authentication Setup Guide

## Overview

Your OpenWebUI is now configured to **require authentication immediately** when users visit. They can log in using:
- **Microsoft OAuth** (recommended)
- **OpenWebUI username/password** (fallback)

## Required Environment Variables in Render

### Already Configured:
- ✅ `WEBUI_AUTH=true` - Forces authentication (no anonymous access)
- ✅ `ENABLE_OAUTH_SIGNUP=true` - Allows Microsoft OAuth signups
- ✅ `ENABLE_LOGIN_FORM=true` - Keeps username/password option available
- ✅ `MICROSOFT_CLIENT_ID` - Your Azure Client ID
- ✅ `MICROSOFT_TENANT_ID` - Your Azure Tenant ID
- ✅ `WEBUI_URL` - Auto-set by Render
- ✅ `MICROSOFT_REDIRECT_URI` - Auto-set by Render
- ✅ `OPENID_PROVIDER_URL` - Microsoft OpenID endpoint

### ⚠️ YOU NEED TO ADD:

**MICROSOFT_CLIENT_SECRET**
- Go to your Render dashboard → Environment tab
- Add new variable:
  - Key: `MICROSOFT_CLIENT_SECRET`
  - Value: [Your Microsoft Client Secret from Azure]
  - Mark as **Secret** ✓

## How to Get Microsoft Client Secret

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Find your app (Client ID: `e1d3755c-410b-4988-b1e5-676afc13e672`)
4. Go to **Certificates & secrets**
5. Create a new **Client secret** (or copy existing one)
6. Copy the **Value** (not the Secret ID)
7. Add it to Render as `MICROSOFT_CLIENT_SECRET`

## Azure App Registration Setup

Make sure your Azure app has:

### Redirect URI:
- **Type**: Web
- **URI**: `https://glchemtec-openwebui.onrender.com/oauth/microsoft/callback`
  (Replace with your actual Render URL after deployment)

### API Permissions:
- `openid`
- `email`
- `profile`
- `User.Read`

### Authentication:
- ✅ Allow public client flows: **No**
- ✅ Supported account types: **Single tenant** (or your preference)

## How It Works

1. **User visits your OpenWebUI URL**
   - Immediately redirected to login page
   - No anonymous access allowed

2. **User clicks "Sign in with Microsoft"**
   - Redirected to Microsoft login
   - Authenticates with Microsoft account
   - Redirected back to OpenWebUI

3. **First-time users**
   - Automatically created as admin (if first user)
   - Or assigned default role based on settings

4. **Subsequent visits**
   - Session remembered (if cookies enabled)
   - Or prompted to login again

## Optional: Microsoft-Only Authentication

If you want to **force Microsoft login only** (disable username/password):

1. In Render dashboard, change:
   - `ENABLE_LOGIN_FORM=false`

This removes the username/password option and only shows Microsoft OAuth.

## Troubleshooting

### OAuth Not Working?
- ✅ Check `MICROSOFT_CLIENT_SECRET` is set correctly
- ✅ Verify redirect URI in Azure matches your Render URL exactly
- ✅ Ensure `WEBUI_URL` matches your actual domain
- ✅ Check Render logs for OAuth errors

### Users Can't Sign Up?
- ✅ Verify `ENABLE_OAUTH_SIGNUP=true`
- ✅ Check Azure app permissions are granted
- ✅ Ensure redirect URI is correct in Azure

### Still Seeing Public Access?
- ✅ Verify `WEBUI_AUTH=true` is set
- ✅ Restart the service in Render after adding env vars
- ✅ Clear browser cache and cookies

## Security Notes

- All secrets are marked as "Secret" in Render (hidden from logs)
- HTTPS is automatically enabled by Render
- Sessions are secured with `WEBUI_SECRET_KEY` (auto-generated)
- First user automatically becomes admin
