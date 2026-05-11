FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including Playwright deps)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    ffmpeg \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser for HTML rendering
RUN playwright install chromium && playwright install-deps chromium

# Create output directories
RUN mkdir -p output/audio output/video output/frames

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
