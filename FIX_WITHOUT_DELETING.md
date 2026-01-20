# Fix Without Deleting Service

## The Real Issue:
- Database has existing users
- Can't create new admin account
- Can't disable WEBUI_AUTH because users exist

## Solution: Override Persistent Config

Add these environment variables in Render:

### Step 1: Force Environment Variables to Override Database

1. **ENABLE_PERSISTENT_CONFIG**
   - Key: `ENABLE_PERSISTENT_CONFIG`
   - Value: `false`
   - This makes env vars override database settings

2. **ENABLE_SIGNUP**
   - Key: `ENABLE_SIGNUP`
   - Value: `true`
   - Allows new signups

3. **ENABLE_LOGIN_FORM**
   - Key: `ENABLE_LOGIN_FORM`
   - Value: `true`
   - Shows login form

4. **ENABLE_PASSWORD_AUTH**
   - Key: `ENABLE_PASSWORD_AUTH`
   - Value: `true`
   - Allows password login

### Step 2: Try to Log In

After adding these and redeploying:

1. Visit your Render URL
2. Try to log in with any existing user account
3. If you can log in, go to Admin Panel and make yourself admin

### Step 3: If You Can't Log In

Try to create a NEW account:
1. The signup form should now be visible
2. Create a new account
3. First new user becomes admin automatically

## Alternative: Clear Database File Only

If Render uses a persistent disk, you might be able to:
1. Go to Render → Your Service → Settings
2. Find "Disks" or "Volumes"
3. Delete just the database volume (not the service)
4. Redeploy

This clears the database but keeps your service.

## What to Add in Render Right Now:

1. `ENABLE_PERSISTENT_CONFIG` = `false`
2. `ENABLE_SIGNUP` = `true`
3. `ENABLE_LOGIN_FORM` = `true`
4. `ENABLE_PASSWORD_AUTH` = `true`

Then redeploy and try to log in or sign up.
