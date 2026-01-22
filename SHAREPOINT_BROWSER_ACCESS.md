# How to Access SharePoint Browser

## Visual File Browser Available! 🎉

I've created a **visual SharePoint browser** that users can access to browse and select files, just like in glc_assistant!

## How to Access

### Step 1: Get Your URL

**If running locally:**
```
http://localhost:8000/sharepoint-browser
```

**If deployed on Render:**
```
https://your-app-name.onrender.com/sharepoint-browser
```

**Note:** The browser is served by the proxy service (port 8000), not OpenWebUI directly.

### Step 2: Open in Browser

Simply open the URL in any web browser. You'll see:

- 📂 **File List** - All files from your SharePoint folder
- 🔍 **Search Bar** - Search for specific files
- 📊 **File Details** - Size, date, file type
- ✅ **Import Button** - Click to import selected file

### Step 3: Browse and Import

1. **Browse** - Scroll through the list of files
2. **Search** - Type in search box and press Enter
3. **Select** - Click on a file to select it (highlighted in blue)
4. **Import** - Click "Import Selected" button
5. **Done!** - File is downloaded and ready for use in OpenWebUI

## Features

✅ **Visual Interface** - See all files at a glance
✅ **Search** - Find files quickly
✅ **File Details** - Size, date, type icons
✅ **One-Click Import** - Select and import easily
✅ **Error Messages** - Clear feedback if something goes wrong

## Integration with OpenWebUI

After importing a file:
1. File is downloaded to the server
2. File is ready to use in OpenWebUI chat
3. You can reference it in your messages
4. Existing filters (PPT/PDF vision) will process it automatically

## Example Workflow

```
1. Open: https://your-app.onrender.com/sharepoint-browser
2. Browse files visually
3. Click on "report_2025.pdf"
4. Click "Import Selected"
5. See: "✅ File imported successfully!"
6. Go to OpenWebUI chat
7. Say: "Analyze the report_2025.pdf file"
8. AI processes the imported file!
```

## Troubleshooting

### "Failed to load files"
- Check SharePoint credentials are set:
  - `SHAREPOINT_CLIENT_ID`
  - `SHAREPOINT_CLIENT_SECRET`
  - `SHAREPOINT_TENANT_ID`
  - `SHAREPOINT_SITE_URL`
  - `ENABLE_SHAREPOINT=true`

### "404 Not Found"
- Make sure you're accessing the proxy port (8000)
- Check that the proxy service is running
- URL should be: `http://your-url:8000/sharepoint-browser`

### "Import failed"
- Check file permissions in SharePoint
- Verify Azure AD app has `Sites.Read.All` permission
- Check server logs for detailed error messages

## Alternative: Chat Commands

If you prefer, you can still use text commands in chat:
- "Import from SharePoint"
- "Load filename.pdf from SharePoint"

But the visual browser is much easier! 🎨

---

**Enjoy browsing SharePoint files visually!** 📂✨
