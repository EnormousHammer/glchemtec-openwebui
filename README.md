# GLChemTec OpenWebUI

Production-ready OpenWebUI deployment for GLChemTec on Render with Python file processing support.

## Features

- ✅ OpenWebUI with full functionality
- ✅ Python support for file processing
- ✅ PDF, PPT, DOCX, XLSX processing capabilities
- ✅ OCR support (Tesseract)
- ✅ Production-ready configuration

## Setup

### Prerequisites
- Render account
- OpenAI API Key
- Microsoft Azure credentials (Client ID and Tenant ID)

### Environment Variables

Set these in your Render dashboard under Environment Variables:

**Required:**
- `OPENAI_API_KEY` - Your OpenAI API key (mark as Secret)
- `MICROSOFT_CLIENT_ID` - Microsoft Azure Client ID (mark as Secret)
- `MICROSOFT_TENANT_ID` - Microsoft Azure Tenant ID (mark as Secret)

**Optional:**
- `WEBUI_NAME` - Display name (default: "GLChemTec OpenWebUI")
- `ENABLE_SIGNUP` - Allow user signups (default: "false")
- `DEFAULT_USER_ROLE` - Default role for new users (default: "admin")

### Deployment

1. Connect your GitHub repository to Render
2. Render will automatically detect `render.yaml` and deploy
3. Set environment variables in Render dashboard
4. Deploy!

The first build may take 10-15 minutes as it installs all dependencies.

## File Processing

This setup includes Python libraries for processing:
- **PDF**: pypdf2, pdfplumber
- **PowerPoint**: python-pptx
- **Word**: python-docx
- **Excel**: openpyxl
- **OCR**: pytesseract (with Tesseract engine)
- **Images**: Pillow

## Local Development

```bash
# Build the Docker image
docker build -t glchemtec-openwebui .

# Run locally
docker run -d \
  -p 8080:8080 \
  -e OPENAI_API_KEY=your_key_here \
  -e MICROSOFT_CLIENT_ID=your_client_id \
  -e MICROSOFT_TENANT_ID=your_tenant_id \
  glchemtec-openwebui
```

## Repository

https://github.com/EnormousHammer/glchemtec-openwebui

## Notes

- Uses Standard plan on Render (recommended for production)
- First deployment takes longer due to dependency installation
- File processing capabilities are ready for PDF/PPT/DOCX/XLSX files
- OCR support included for image-based PDFs
