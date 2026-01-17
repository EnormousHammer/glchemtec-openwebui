# Use the official OpenWebUI Docker image as base
FROM ghcr.io/open-webui/open-webui:main

# Install Python and essential libraries for file processing
USER root

# Install system dependencies for PDF/PPT processing, audio, and more
# Includes EMF/WMF support for better PowerPoint image rendering
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    poppler-utils \
    libreoffice \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-draw \
    tesseract-ocr \
    tesseract-ocr-eng \
    ffmpeg \
    libsndfile1 \
    # EMF/WMF and vector graphics support
    libwmf-dev \
    libwmf-bin \
    libwmf0.2-7 \
    imagemagick \
    ghostscript \
    # Better font support for accurate rendering
    fonts-liberation \
    fonts-liberation2 \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    fonts-noto \
    # SVG support
    librsvg2-bin \
    && rm -rf /var/lib/apt/lists/* \
    # Configure ImageMagick to allow PDF processing
    && sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml 2>/dev/null || true

# Install Python libraries for full document processing (ChatGPT-like capabilities)
RUN pip3 install --no-cache-dir \
    # PDF processing
    pypdf2 \
    pdfplumber \
    pymupdf \
    pdf2image \
    # Office documents
    python-pptx \
    python-docx \
    openpyxl \
    xlrd \
    # Data processing
    pandas \
    numpy \
    # Images and OCR
    pillow \
    pytesseract \
    # Web/HTML/Markdown
    markdown \
    beautifulsoup4 \
    lxml \
    html2text \
    # NLP and text processing
    nltk \
    chardet \
    # CSV and data formats
    csvkit \
    # Audio transcription (if needed)
    pydub \
    # File type detection
    python-magic \
    # Archive handling
    rarfile \
    py7zr \
    # PDF generation for exports
    reportlab \
    # Chart and graph generation
    matplotlib \
    plotly \
    kaleido \
    seaborn

# Create directories with proper permissions for NLTK and other data
RUN mkdir -p /home/user/nltk_data && \
    mkdir -p /app/data && \
    mkdir -p /app/uploads && \
    mkdir -p /tmp/libreoffice && \
    chmod -R 777 /home/user/nltk_data && \
    chmod -R 777 /app/data && \
    chmod -R 777 /app/uploads && \
    chmod -R 777 /tmp/libreoffice

# Download NLTK data
RUN python3 -c "import nltk; nltk.download('punkt', download_dir='/home/user/nltk_data'); nltk.download('averaged_perceptron_tagger', download_dir='/home/user/nltk_data'); nltk.download('stopwords', download_dir='/home/user/nltk_data')" || true

# Set environment variables for data directories
ENV NLTK_DATA=/home/user/nltk_data
ENV HOME=/home/user

# Fix permissions for static files and directories
RUN chown -R 1000:1000 /app/backend/open_webui/static 2>/dev/null || true && \
    chmod -R 755 /app/backend/open_webui/static 2>/dev/null || true && \
    chmod 666 /app/.webui_secret_key 2>/dev/null || true && \
    chown -R 1000:1000 /home/user 2>/dev/null || true && \
    chown -R 1000:1000 /app/data 2>/dev/null || true && \
    chown -R 1000:1000 /app/uploads 2>/dev/null || true

# Switch back to the original user
USER 1000

# Expose port (Render will set PORT env var)
EXPOSE 8080

# The base image handles the start command
# WEBUI_SECRET_KEY should be set as environment variable, not file
