FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV MUSIC_PATH=/music
ENV CONFIG_PATH=/config
ENV CACHE_PATH=/cache
ENV LOGS_PATH=/logs

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    wget \
    git \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /music /config /cache /logs

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Make scripts executable
RUN chmod +x bin/* scripts/*

# Create symbolic links for easier access
RUN ln -sf /app/bin/download_music /usr/local/bin/download_music && \
    ln -sf /app/bin/fixalbumart_improved /usr/local/bin/fixalbumart_improved && \
    ln -sf /app/batch_metadata.py /usr/local/bin/batch_metadata

# Create entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set proper ownership
RUN chown -R 1000:1000 /app /music /config /cache /logs

# Switch to non-root user
USER 1000:1000

# Expose port for potential web interface
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import eyed3, requests; print('OK')" || exit 1

# Default command
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["/bin/bash"]
