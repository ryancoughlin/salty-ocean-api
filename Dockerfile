FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for cfgrib
RUN apt-get update && apt-get install -y \
    libeccodes0 \
    libeccodes-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 5010

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5010"] 