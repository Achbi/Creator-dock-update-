FROM python:3.10-slim

# System deps (ffmpeg for merging A/V)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Expose port
EXPOSE 10000

# Start app
CMD ["bash", "-lc", "gunicorn yt:app --bind 0.0.0.0:${PORT:-10000}"]
