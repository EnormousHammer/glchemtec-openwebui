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

# Install Python libraries from requirements
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy proxy script, filters, and startup script
COPY openai_responses_proxy.py /app/openai_responses_proxy.py
# Place filters in both default locations to ensure auto-load
COPY export_filter.py /app/backend/filters/export_filter.py
COPY export_filter.py /app/backend/custom/filters/export_filter.py
COPY ppt_pdf_filter.py /app/backend/filters/ppt_pdf_filter.py
COPY ppt_pdf_filter.py /app/backend/custom/filters/ppt_pdf_filter.py
COPY sharepoint_import_filter.py /app/backend/filters/sharepoint_import_filter.py
COPY sharepoint_import_filter.py /app/backend/custom/filters/sharepoint_import_filter.py
COPY public/GLC_Logo.png /app/backend/open_webui/static/branding/GLC_Logo.png
COPY public/GLC_icon.png /app/backend/open_webui/static/branding/GLC_icon.png
COPY public/branding/glc-theme.css /app/backend/open_webui/static/branding/glc-theme.css
COPY start.sh /app/start.sh
COPY set_default_connection.py /app/set_default_connection.py
COPY set_connection_on_startup.py /app/set_connection_on_startup.py

# Modify OpenWebUI's startup script to start proxy first
# Use printf instead of heredoc - more reliable in Dockerfile RUN commands
RUN set -e && \
    mkdir -p /app/backend/open_webui/static/branding /app/backend/open_webui/static/css && \
    # Set favicon to GLC icon
    cp /app/backend/open_webui/static/branding/GLC_icon.png /app/backend/open_webui/static/favicon.ico && \
    if [ -f /app/backend/start.sh ]; then \
        cp /app/backend/start.sh /app/backend/start.sh.original && \
        printf '#!/bin/bash\nset -e\ncd /app\necho "=== Starting OpenAI Responses Proxy ==="\npython3 -m uvicorn openai_responses_proxy:app --host 0.0.0.0 --port 8000 2>&1 &\nPROXY_PID=$!\necho "Proxy started with PID: $PROXY_PID"\nsleep 3\nif ! kill -0 $PROXY_PID 2>/dev/null; then\n  echo "ERROR: Proxy process died immediately!"\n  wait $PROXY_PID 2>/dev/null || true\n  exit 1\nelse\n  echo "✓ Proxy is running (PID: $PROXY_PID)"\nfi\necho "=== Starting OpenWebUI ==="\npython3 /app/set_connection_on_startup.py > /tmp/connection_setup.log 2>&1 &\nexec bash /app/backend/start.sh.original "$@"\n' > /app/backend/start.sh && \
        chmod +x /app/backend/start.sh && \
        echo "✓ Successfully modified /app/backend/start.sh"; \
    else \
        echo "⚠️ WARNING: /app/backend/start.sh not found - proxy injection skipped"; \
    fi

# Create directories with proper permissions for NLTK and other data
RUN mkdir -p /home/user/nltk_data && \
    mkdir -p /app/data && \
    mkdir -p /app/uploads && \
    mkdir -p /tmp/libreoffice && \
    mkdir -p /app/backend/filters && \
    mkdir -p /app/backend/custom/filters && \
    chmod -R 777 /home/user/nltk_data && \
    chmod -R 777 /app/data && \
    chmod -R 777 /app/uploads && \
    chmod -R 777 /tmp/libreoffice && \
    chmod -R 755 /app/backend && \
    chmod +x /app/openai_responses_proxy.py && \
    chmod +x /app/start.sh && \
    chmod +x /app/set_default_connection.py && \
    chmod +x /app/set_connection_on_startup.py

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

# Expose ports (8080 for OpenWebUI, 8000 for proxy)
EXPOSE 8080 8000

# Use base image's default entrypoint (it will call /app/backend/start.sh which we modified)
