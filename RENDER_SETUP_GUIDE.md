# Step-by-Step Render Setup Guide

## Prerequisites
- Render account (sign up at https://render.com if you don't have one)
- GitHub repository connected to Render
- Your credentials ready (already saved in credentials.txt)

---

## Step 1: Create a New Web Service on Render

1. **Log in to Render Dashboard**
   - Go to https://dashboard.render.com
   - Sign in with your account

2. **Create New Web Service**
   - Click the **"New +"** button (top right)
   - Select **"Web Service"**

3. **Connect Your Repository**
   - Choose **"Build and deploy from a Git repository"**
   - Click **"Connect account"** if you haven't connected GitHub yet
   - Authorize Render to access your GitHub repositories
   - Select your repository: **`EnormousHammer/glchemtec-openwebui`**

---

## Step 2: Configure the Service

### Basic Settings:
- **Name**: `glchemtec-openwebui` (or your preferred name)
- **Region**: Choose closest to you (Oregon, Frankfurt, Singapore, etc.)
- **Branch**: `main` (or your default branch)
- **Root Directory**: Leave empty (or `./` if needed)
- **Runtime**: Select **"Docker"**

### Build & Deploy Settings:
- **Dockerfile Path**: `./Dockerfile` (should auto-detect)
- **Docker Context**: `.` (root directory)
- **Build Command**: Leave empty (Docker handles this)
- **Start Command**: Leave empty (Docker handles this)

### Plan Selection:
- **Standard Plan**: $7/month (recommended - this setup uses Standard for better performance with file processing)
- **Starter Plan**: Free tier (can work but slower for file processing)

---

## Step 3: Set Environment Variables

Click on **"Environment"** tab and add these variables:

### Required Variables:

1. **OPENAI_API_KEY**
   - Key: `OPENAI_API_KEY`
   - Value: `your_openai_api_key_here` (get from credentials.txt)
   - Mark as **Secret** ✓

2. **MICROSOFT_CLIENT_ID**
   - Key: `MICROSOFT_CLIENT_ID`
   - Value: `your_microsoft_client_id_here` (get from credentials.txt)
   - Mark as **Secret** ✓

3. **MICROSOFT_CLIENT_SECRET** ⚠️ **REQUIRED FOR AUTH**
   - Key: `MICROSOFT_CLIENT_SECRET`
   - Value: Get from Azure Portal → App registrations → Your app → Certificates & secrets
   - Mark as **Secret** ✓
   - **You must add this manually - it's not in credentials.txt**

4. **MICROSOFT_TENANT_ID**
   - Key: `MICROSOFT_TENANT_ID`
   - Value: `your_microsoft_tenant_id_here` (get from credentials.txt)
   - Mark as **Secret** ✓

### Auto-Configured Variables (Set by render.yaml):
- `WEBUI_AUTH=true` - Forces login immediately
- `ENABLE_OAUTH_SIGNUP=true` - Allows Microsoft signups
- `ENABLE_LOGIN_FORM=true` - Keeps username/password option
- `WEBUI_URL` - Auto-set from your Render URL
- `MICROSOFT_REDIRECT_URI` - Auto-set to your callback URL
- `OPENID_PROVIDER_URL` - Microsoft OpenID endpoint

### Optional Variables:

5. **WEBUI_NAME**
   - Key: `WEBUI_NAME`
   - Value: `GLChemTec OpenWebUI`
   - Not secret (already in render.yaml)

**Note:** If you want Microsoft-only login (no username/password), you can manually add:
- `ENABLE_LOGIN_FORM=false` in Render dashboard

---

## Step 4: Advanced Settings (Optional)

### Health Check:
- **Health Check Path**: `/health` or `/` (check OpenWebUI docs)
- Leave empty if unsure, Render will use defaults

### Auto-Deploy:
- **Auto-Deploy**: Enabled ✓ (deploys on every push to main branch)
- Or disable if you want manual deployments

### Headers:
- Usually not needed for basic setup

---

## Step 5: Create the Service

1. **Review Settings**
   - Double-check all environment variables are set
   - Verify Dockerfile path is correct

2. **Click "Create Web Service"**
   - Render will start building your service
   - This may take 5-10 minutes the first time

3. **Monitor the Build**
   - Watch the build logs in real-time
   - **First build takes 10-15 minutes** - it installs Python, LibreOffice, Tesseract, and all file processing libraries
   - Be patient, this is normal for the first deployment

---

## Step 6: Wait for Deployment

1. **Build Process**
   - Render pulls your code from GitHub
   - Builds the Docker container
   - Sets up the service

2. **Deployment Complete**
   - You'll see "Live" status when ready
   - Your service URL will be: `https://glchemtec-openwebui.onrender.com` (or your custom name)

3. **Access Your Service**
   - Click on the service URL
   - OpenWebUI should be accessible

---

## Step 7: Verify Everything Works

1. **Test the Service**
   - Open the service URL in your browser
   - You should see the OpenWebUI interface

2. **Check Logs**
   - Go to "Logs" tab in Render dashboard
   - Look for any errors or warnings
   - Verify environment variables are loaded

3. **Test OpenAI Integration**
   - Try using the chat interface
   - Verify OpenAI API is working

---

## Troubleshooting

### If Build Fails:
- Check Dockerfile path is correct
- Verify Dockerfile exists in your repository
- Check build logs for specific errors

### If Service Won't Start:
- Check environment variables are all set
- Verify all required secrets are marked as "Secret"
- Check logs for startup errors

### If OpenAI Not Working:
- Verify OPENAI_API_KEY is correct
- Check it's marked as "Secret" in Render
- Look for API errors in logs

### If Service Goes to Sleep (Free Tier):
- Free tier services sleep after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- Consider upgrading to Standard plan for always-on service

---

## Next Steps After Deployment

1. **Set Up Custom Domain** (Optional)
   - Go to Settings → Custom Domains
   - Add your domain if you have one

2. **Enable HTTPS**
   - Render provides free SSL certificates automatically
   - HTTPS is enabled by default

3. **Monitor Usage**
   - Check the Metrics tab for resource usage
   - Monitor costs if on paid plan

4. **Set Up Backups** (if using database)
   - Configure database backups if needed
   - OpenWebUI may need persistent storage for data

---

## Quick Reference: Environment Variables Checklist

**Required:**
- [ ] OPENAI_API_KEY (Secret)
- [ ] MICROSOFT_CLIENT_ID (Secret)
- [ ] MICROSOFT_TENANT_ID (Secret)

**Recommended:**
- [ ] WEBUI_NAME
- [ ] ENABLE_SIGNUP
- [ ] DEFAULT_USER_ROLE

## What's Included in This Setup

✅ **OpenWebUI** - Full UI and functionality  
✅ **Python 3** - For custom file processing  
✅ **PDF Processing** - pypdf2, pdfplumber  
✅ **PowerPoint Processing** - python-pptx  
✅ **Word/Excel Processing** - python-docx, openpyxl  
✅ **OCR Support** - Tesseract + pytesseract  
✅ **Image Processing** - Pillow  
✅ **Production Ready** - Standard plan, health checks, auto-deploy

---

## Support

If you run into issues:
1. Check Render documentation: https://render.com/docs
2. Check OpenWebUI documentation: https://docs.openwebui.com
3. Review build and runtime logs in Render dashboard
