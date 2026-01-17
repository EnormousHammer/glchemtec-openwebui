# Use the official OpenWebUI Docker image as base
FROM ghcr.io/open-webui/open-webui:main

# Install Python and essential libraries for file processing
USER root

# Install system dependencies for PDF/PPT processing
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    poppler-utils \
    libreoffice \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install Python libraries for document processing
RUN pip3 install --no-cache-dir \
    pypdf2 \
    pdfplumber \
    python-pptx \
    python-docx \
    openpyxl \
    pillow \
    pytesseract \
    markdown \
    beautifulsoup4 \
    lxml

# Switch back to the original user
USER 1000

# Expose port (Render will set PORT env var)
EXPOSE 8080

# The base image handles the start command