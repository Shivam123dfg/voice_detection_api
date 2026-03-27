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

# Pre-download the model at build time so it's cached in the image
RUN python -c "from transformers import pipeline; pipeline('audio-classification', model='MelodyMachine/Deepfake-audio-detection-V2')"

# Copy application code
COPY . .

# Expose port
EXPOSE 10000

# Start the application (single worker to limit memory usage)
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "1000", "voice_detection_api:app"]