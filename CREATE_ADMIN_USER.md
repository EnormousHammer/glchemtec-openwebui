# Create Admin User: haron alhakimi

## Method 1: Create via OpenWebUI UI (Easiest)

If authentication is not yet enabled:

1. **Visit your Render URL**
   - Go to: `https://glchemtec-openwebui.onrender.com`

2. **Sign Up/Create Account**
   - If you see a signup page, create an account with:
     - **Name/Username**: `haron alhakimi`
     - **Email**: Your email
     - **Password**: `Alhakimi2016!`
   - The first user is automatically admin

3. **If signup is disabled:**
   - Temporarily set `ENABLE_SIGNUP=true` in Render
   - Create the account
   - Set `ENABLE_SIGNUP=false` again (optional)

## Method 2: Create via Environment Variables (First User)

Add these to Render → Environment Variables:

1. **DEFAULT_USER_EMAIL**
   - Value: `haron@example.com` (or your email)
   - Not secret

2. **DEFAULT_USER_NAME**
   - Value: `haron alhakimi`
   - Not secret

3. **DEFAULT_USER_PASSWORD**
   - Value: `Alhakimi2016!`
   - **Mark as Secret** ✓

4. **DEFAULT_USER_ROLE**
   - Value: `admin`
   - Not secret

5. **ENABLE_SIGNUP**
   - Value: `true` (temporarily, to create the user)
   - Not secret

Then:
- Redeploy the service
- The user will be created automatically
- You can then set `ENABLE_SIGNUP=false` if you want

## Method 3: Create via Docker Exec (If accessible)

If you have shell access to the container:

```bash
# This would require direct container access
# Usually not available on Render
```

## Recommended: Method 1 (UI Signup)

**Steps:**
1. Go to Render Dashboard → Environment
2. Make sure `ENABLE_SIGNUP=true` (or add it)
3. Make sure `WEBUI_AUTH=false` temporarily (or remove it)
4. Save and redeploy
5. Visit your Render URL
6. Click "Sign Up" or "Create Account"
7. Enter:
   - Name: `haron alhakimi`
   - Email: Your email
   - Password: `Alhakimi2016!`
8. First user becomes admin automatically
9. (Optional) Set `ENABLE_SIGNUP=false` and `WEBUI_AUTH=true` after

## After Creating User

Once the user is created:
- Log in with: `haron alhakimi` / `Alhakimi2016!`
- You'll have admin access
- You can manage other users from the admin panel

## Security Note

After creating the admin user:
- Consider setting `ENABLE_SIGNUP=false` to prevent public signups
- Keep `WEBUI_AUTH=true` to require login
- The password is stored securely in the database
