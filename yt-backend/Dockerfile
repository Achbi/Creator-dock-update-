# Use Python 3.10 slim image for smaller size and better performance
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including ffmpeg for video processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create downloads directory with proper permissions
RUN mkdir -p downloads && \
    chown -R app:app /app

# Copy application files
COPY . .

# Change ownership of all files to app user
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Expose the port
EXPOSE 10000

# Health check to ensure the service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Start the application with gunicorn
# Using single worker to prevent memory issues on small instances
# Extended timeout for video processing
CMD ["bash", "-c", "gunicorn yt:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 300 --worker-class sync --max-requests 1000 --max-requests-jitter 100 --preload --log-level info --access-logfile - --error-logfile -"]