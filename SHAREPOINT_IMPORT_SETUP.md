# SharePoint Import Filter Setup Guide

## Overview

The SharePoint Import Filter allows you to import files from SharePoint directly into your chat for analysis. Simply ask to import a file from SharePoint, and it will be downloaded and made available for analysis.

## Features

- **Browse SharePoint Files**: List files available in SharePoint folders
- **Import Specific Files**: Download files by name for analysis
- **Automatic Download**: Files are automatically downloaded to your system
- **Seamless Integration**: Imported files work with all existing analysis features (PPT/PDF vision, etc.)

## Prerequisites

### 1. SharePoint Configuration

You need:
- SharePoint site URL
- Azure AD app registration with SharePoint permissions
- Client ID, Client Secret, and Tenant ID

### 2. Environment Variables

Add these to your `.env` file or Render dashboard:

```bash
# SharePoint Import Configuration
ENABLE_SHAREPOINT=true
SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/YourSite
SHAREPOINT_FOLDER=Documents
SHAREPOINT_CLIENT_ID=your_client_id
SHAREPOINT_CLIENT_SECRET=your_client_secret
SHAREPOINT_TENANT_ID=your_tenant_id
```

### 3. Azure AD App Registration

1. Go to Azure Portal → Azure Active Directory → App registrations
2. Create a new app registration
3. Create a client secret
4. Grant API permissions:
   - `Sites.ReadWrite.All` (Application permission)
   - Or `Sites.Selected` with specific site access
5. Note down:
   - Application (client) ID
   - Directory (tenant) ID
   - Client secret value

## ⚠️ IMPORTANT: No Function Registration Needed!

**The SharePoint Import is a FILTER, not a Function:**
- ✅ **Auto-loads** from `/app/backend/filters/` directory
- ✅ **No manual registration** required
- ✅ **Already configured** in Dockerfile
- ❌ **Do NOT** try to add it as a function in Admin UI

**How to Verify It's Loaded:**
1. Check Render logs for: `[SHAREPOINT-IMPORT] SharePoint import filter initialized`
2. If you see this message, the filter is loaded and working
3. You can configure it in **Admin → Functions** (it will appear there), but it auto-loads regardless

## Usage

### Option 1: Visual Browser (Recommended) 🌟

**Access the visual SharePoint browser:**

1. Open your browser and go to:
   ```
   http://your-openwebui-url:8000/sharepoint-browser
   ```
   Or if using Render:
   ```
   https://your-render-url.onrender.com/sharepoint-browser
   ```

2. You'll see a visual file browser with:
   - 📂 List of all SharePoint files
   - 🔍 Search functionality
   - 📄 File details (size, date)
   - ✅ Click to select and import files

3. Click on any file to select it, then click "Import Selected"

4. The file will be downloaded and ready to use in OpenWebUI chat!

### Option 2: Text-Based (Chat Commands)

You can also use chat commands:

- **"Import from SharePoint"** - Lists available files
- **"Load file.pdf from SharePoint"** - Downloads specific file
- **"Get document.docx from SharePoint"** - Downloads specific file
- **"Browse SharePoint files"** - Lists files in folder

### Example Conversation

```
You: Import from SharePoint

Assistant: I found the following files in SharePoint:
- report_2025.pdf (245KB)
- analysis.docx (89KB)
- presentation.pptx (1.2MB)
Which file would you like to import for analysis?

You: Load report_2025.pdf from SharePoint

Assistant: I've imported 'report_2025.pdf' from SharePoint. The file is now attached and ready for analysis.
[File attached: report_2025.pdf]

You: Analyze this document

Assistant: [Analyzes the imported PDF...]
```

## How It Works

1. **Request Detection**: Filter detects SharePoint import requests in your message
2. **File Listing**: If no specific file mentioned, lists available files
3. **File Download**: Downloads the requested file from SharePoint
4. **Local Storage**: Saves file to uploads directory
5. **File Attachment**: Attaches file to your message for analysis
6. **Analysis**: File is processed by existing analysis filters (PPT/PDF vision, etc.)

## Configuration

### Filter Settings (OpenWebUI Admin)

Configure in **Admin** → **Functions** → **SharePoint Import Filter**:

```json
{
  "enabled": true,
  "enable_sharepoint": true,
  "sharepoint_site_url": "https://yourcompany.sharepoint.com/sites/YourSite",
  "sharepoint_folder": "Documents",
  "debug": true
}
```

### Folder Paths

The filter looks for files in the configured SharePoint folder:
- Default: `Documents`
- Custom: Set via `SHAREPOINT_FOLDER` environment variable
- Path format: `Folder/Subfolder` (no leading/trailing slashes)

## Supported File Types

All file types supported by your analysis system:
- **PDFs**: Full vision analysis
- **Word Documents**: Text extraction and analysis
- **PowerPoint**: Slide extraction and vision analysis
- **Excel**: Data analysis
- **Images**: Vision analysis
- **And more**: Any file type your system supports

## Troubleshooting

### "SharePoint credentials not configured"
- Check that all environment variables are set:
  - `SHAREPOINT_CLIENT_ID`
  - `SHAREPOINT_CLIENT_SECRET`
  - `SHAREPOINT_TENANT_ID`
  - `SHAREPOINT_SITE_URL`

### "File not found in SharePoint"
- Verify the file exists in the configured folder
- Check folder path is correct
- Ensure file name matches exactly (case-sensitive)

### "Token request failed"
- Verify Azure AD app has correct permissions
- Check client secret hasn't expired
- Ensure tenant ID is correct

### "Failed to download file"
- Check file size (very large files may timeout)
- Verify SharePoint site URL is accessible
- Check network connectivity

## Security Notes

- Files are downloaded to the uploads directory (same as regular uploads)
- Files are accessible only to authenticated users
- SharePoint credentials should be kept secure
- Consider using environment variables or secrets management

## File Naming

Downloaded files are renamed to avoid conflicts:
- Format: `sharepoint_{original_name}_{timestamp}.{ext}`
- Example: `sharepoint_report_2025_20250121_143022.pdf`
- Original filename is preserved in metadata

## Integration with Other Filters

The SharePoint Import Filter works seamlessly with:
- **PPT/PDF Vision Filter**: Imported PPT/PDF files are automatically processed
- **Export Filter**: You can export analyzed documents back to SharePoint
- **File Analysis**: All standard file analysis features work on imported files

## Advanced Usage

### Import Multiple Files

You can import multiple files in sequence:
```
You: Import report.pdf from SharePoint
[File imported]

You: Now import analysis.docx from SharePoint
[File imported]

You: Analyze both documents
[Analyzes both files]
```

### Custom Folders

Specify different folders in your request:
```
You: Import from SharePoint folder "Project Documents"
```

(Note: Currently uses configured default folder. Custom folder selection can be added.)

## Best Practices

1. **Organize SharePoint**: Keep files organized in folders for easier access
2. **File Naming**: Use descriptive filenames for easier identification
3. **File Size**: Be mindful of large files (may take longer to download)
4. **Permissions**: Ensure Azure AD app has access to required SharePoint folders

## Future Enhancements

Potential additions:
- Browse subfolders
- Search files by name/type
- Import multiple files at once
- Preview files before import
- Sync files automatically
- File versioning support

---

**Enjoy importing files from SharePoint for analysis!** ☁️📄
