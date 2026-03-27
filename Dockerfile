FROM python:3.11-slim

# Install system dependencies (ffmpeg, libsndfile)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libsndfile1-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Use a fixed cache directory (HF Spaces runs as non-root user 1000)
ENV HF_HOME=/app/model_cache
ENV HF_HUB_DISABLE_XET=1

# Copy requirements and install Python dependencies
COPY requirements_voice_api.txt .
RUN pip install --no-cache-dir -r requirements_voice_api.txt

# Pre-download the model at build time into the fixed cache location
RUN python -c "from transformers import pipeline; pipeline('audio-classification', model='MelodyMachine/Deepfake-audio-detection-V2')"

# Make cache readable by any user (HF Spaces runs as uid 1000)
RUN chmod -R 777 /app/model_cache

# Copy application code
COPY . .

# Default port (HuggingFace Spaces uses 7860)
ENV PORT=7860
EXPOSE 7860

# Start the application (single worker to limit memory usage)
CMD gunicorn --bind 0.0.0.0:${PORT} --workers 1 --timeout 300 --log-level info voice_detection_api:app