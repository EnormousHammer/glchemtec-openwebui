# Admin User Setup: haron alhakimi

## ✅ Configuration Added

I've added the environment variables to auto-create the admin user. Here's what you need to do:

## Steps to Create Admin User

### Step 1: Add Password to Render

1. Go to Render Dashboard → Your Service → **Environment** tab
2. Add this variable:
   - **Key**: `WEBUI_ADMIN_PASSWORD`
   - **Value**: `Alhakimi2016!`
   - **Mark as Secret** ✓

### Step 2: Verify Other Variables

The following are already configured in `render.yaml`:
- ✅ `WEBUI_ADMIN_EMAIL` = `haron@glchemtec.com`
- ✅ `ENABLE_SIGNUP` = `false` (prevents public signups)

### Step 3: Redeploy

1. Save the `WEBUI_ADMIN_PASSWORD` variable in Render
2. Trigger a manual redeploy (or wait for auto-deploy from git push)
3. Wait for deployment to complete

### Step 4: Log In

After redeploy, the admin user will be automatically created. Log in with:

- **Email/Username**: `haron@glchemtec.com` or `haron alhakimi`
- **Password**: `Alhakimi2016!`

## What Happens

- On first startup with these variables, OpenWebUI will automatically create the admin user
- The user will have full admin privileges
- Public signups will be disabled (`ENABLE_SIGNUP=false`)

## If You Want to Change the Email

If you want a different email address:

1. Update `WEBUI_ADMIN_EMAIL` in Render to your preferred email
2. Or update it in `render.yaml` and push to git

## After Login

Once logged in as admin, you can:
- ✅ Manage other users
- ✅ Configure settings
- ✅ Set up OAuth (if not done yet)
- ✅ Access all admin features

## Security Notes

- The password is stored securely (hashed) in the database
- Only the first user created this way becomes admin
- After the admin is created, you can enable signups if needed by setting `ENABLE_SIGNUP=true`
