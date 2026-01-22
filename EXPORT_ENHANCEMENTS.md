# Export System Enhancements - Branding, Visuals & SharePoint Integration

## Overview

The export system has been enhanced with professional branding, visual customization, and SharePoint integration to provide a more polished, enterprise-ready document export experience similar to modern platforms like SharePoint.

## ✨ New Features

### 1. **Branding & Customization**

#### Company Branding
- **Company Name**: Customizable company name displayed in documents
- **Logo Support**: Add your company logo to PDF and Word documents
- **Color Scheme**: Customizable primary and secondary brand colors
  - Primary color: Used for headers, titles, and accents
  - Secondary color: Used for backgrounds and highlights

#### Visual Enhancements
- **Document Type Icons**: Visual indicators (📄 PDF, 📝 Word) in messages
- **Branded Headers**: Colored header bars with company branding
- **Professional Tables**: Enhanced table styling with brand colors and alternating row colors
- **Section Dividers**: Visual separators between document sections

### 2. **SharePoint Integration**

#### Automatic Upload
- Documents can be automatically uploaded to SharePoint after generation
- Configurable SharePoint site URL and folder path
- Secure authentication using Azure AD credentials

#### Features
- Automatic file upload to specified SharePoint folder
- Returns SharePoint URL for easy access
- Displays SharePoint link in chat response
- Graceful fallback if SharePoint is unavailable

### 3. **Enhanced Document Generation**

#### PDF Enhancements
- Branded header with company colors
- Logo integration at top of document
- Professional color-coded sections
- Enhanced table styling with brand colors
- Alternating row colors for better readability

#### Word Document Enhancements
- Branded title with company colors
- Logo support
- Color-coded section headings
- Professional formatting throughout

## 🔧 Configuration

### Environment Variables

Add these to your `.env` file or Render dashboard:

```bash
# Company Branding
COMPANY_NAME=GLChemTec
COMPANY_LOGO_PATH=/app/public/glc_claude.png
PRIMARY_COLOR=#1d2b3a
SECONDARY_COLOR=#e6eef5

# SharePoint Integration (Optional)
SHAREPOINT_CLIENT_ID=your_client_id
SHAREPOINT_CLIENT_SECRET=your_client_secret
SHAREPOINT_TENANT_ID=your_tenant_id
```

### Filter Settings (OpenWebUI Admin)

Configure in **Admin** → **Functions** → **Document Export Filter**:

```json
{
  "enabled": true,
  "company_name": "GLChemTec",
  "company_logo_path": "/app/public/glc_claude.png",
  "primary_color": "#1d2b3a",
  "secondary_color": "#e6eef5",
  "enable_sharepoint": true,
  "sharepoint_site_url": "https://yourcompany.sharepoint.com/sites/YourSite",
  "sharepoint_folder": "Documents/Exports"
}
```

## 📋 Usage

### Basic Export

Simply ask in chat:
- "Export this conversation to PDF"
- "Create a Word document"
- "Generate a PDF file"

### What You Get

1. **Professional Document** with:
   - Your company branding
   - Logo (if configured)
   - Brand colors throughout
   - Visual document type indicator

2. **Downloadable Attachment** in chat:
   - File appears as attachment (like ChatGPT)
   - Click to download directly
   - File size and format displayed

3. **SharePoint Upload** (if enabled):
   - Automatic upload to SharePoint
   - Direct link to SharePoint file
   - Accessible from anywhere

## 🎨 Visual Features

### Document Type Indicators
- 📄 PDF exports
- 📝 Word/DOCX exports

### Branded Elements
- **Header Bar**: Colored bar with document title
- **Section Headings**: Color-coded with brand primary color
- **Tables**: Brand-colored headers with alternating rows
- **Logo**: Company logo at top of document (if provided)

### Color Customization

The system uses your brand colors throughout:
- **Primary Color**: Headers, titles, table headers, section headings
- **Secondary Color**: Table backgrounds, dividers, accents

## ☁️ SharePoint Setup

### Prerequisites

1. **Azure AD App Registration**:
   - Register an app in Azure AD
   - Grant SharePoint permissions
   - Create client secret

2. **SharePoint Site**:
   - Create or identify target SharePoint site
   - Note the site URL
   - Create target folder (e.g., "Documents/Exports")

### Configuration Steps

1. **Get Azure AD Credentials**:
   ```
   SHAREPOINT_CLIENT_ID=your-app-client-id
   SHAREPOINT_CLIENT_SECRET=your-app-secret
   SHAREPOINT_TENANT_ID=your-tenant-id
   ```

2. **Set SharePoint URL**:
   ```
   sharepoint_site_url=https://yourcompany.sharepoint.com/sites/YourSite
   sharepoint_folder=Documents/Exports
   ```

3. **Enable in Filter Settings**:
   ```json
   {
     "enable_sharepoint": true,
     "sharepoint_site_url": "https://yourcompany.sharepoint.com/sites/YourSite",
     "sharepoint_folder": "Documents/Exports"
   }
   ```

### SharePoint Permissions Required

Your Azure AD app needs:
- `Sites.ReadWrite.All` (Application permission)
- Or `Sites.Selected` with specific site access

## 📝 Example Output

### Chat Response
```
📄 **Export Ready**: I've generated a professional PDF document 'export_20250121_123456.pdf' (45KB) 
with GLChemTec branding. You can download it using the attachment below.

☁️ **SharePoint**: Document uploaded to SharePoint
[Download attachment: export_20250121_123456.pdf]
```

### Document Features
- Professional header with company name
- Branded color scheme throughout
- Logo at top (if configured)
- Clean, organized sections
- Professional tables with brand colors
- Footer with company information

## 🔍 Troubleshooting

### Logo Not Appearing
- Check `COMPANY_LOGO_PATH` points to valid image file
- Ensure image is accessible (PNG, JPG supported)
- Check file permissions

### SharePoint Upload Failing
- Verify Azure AD credentials are correct
- Check SharePoint site URL is accessible
- Ensure app has proper permissions
- Check folder path exists in SharePoint

### Colors Not Applying
- Verify color format is hex (e.g., `#1d2b3a`)
- Check filter settings are saved
- Restart OpenWebUI if changes don't appear

## 🚀 Future Enhancements

Potential additions:
- Custom document templates
- Watermark support
- Multiple logo positions
- Custom fonts
- Document themes
- Batch export capabilities
- Email integration
- OneDrive integration

## 📚 Technical Details

### Files Modified
- `export_filter.py`: Enhanced with branding and SharePoint integration
- `openai_responses_proxy.py`: Enhanced PDF/DOCX generation with branding

### Dependencies
- All existing dependencies (no new packages required)
- SharePoint integration uses standard `requests` library

### Backward Compatibility
- All enhancements are optional
- Default behavior maintained if branding not configured
- Existing exports continue to work

## 🎯 Best Practices

1. **Logo**: Use high-quality PNG or JPG, recommended size 200-400px width
2. **Colors**: Choose colors with good contrast for readability
3. **SharePoint**: Use dedicated folder for exports to keep organized
4. **Naming**: Documents are auto-named with timestamps to avoid conflicts

---

**Enjoy your enhanced, branded document exports!** 🎨📄
