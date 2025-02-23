FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libeccodes0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data downloaded_data cache/gfs_wave

# Expose port
EXPOSE 5010

# Run the application with gunicorn
CMD ["gunicorn", "main:app", "--config", "gunicorn_conf.py", "--worker-class", "uvicorn.workers.UvicornWorker"] 