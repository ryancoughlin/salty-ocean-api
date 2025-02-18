FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for GRIB2 processing
RUN apt-get update && apt-get install -y \
    libeccodes0 \
    libeccodes-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/tmp/gfs_wind

# Expose the port the app runs on
EXPOSE 5010

# Command to run the application with Gunicorn in production
CMD ["gunicorn", "-c", "gunicorn_conf.py", "main:app"] 