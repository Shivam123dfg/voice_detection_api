FROM python:3.11-slim

# Install system dependencies (ffmpeg, libsndfile)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libsndfile1-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements_voice_api.txt .
RUN pip install --no-cache-dir -r requirements_voice_api.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 10000

# Start the application
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "2", "--timeout", "300", "voice_detection_api:app"]
