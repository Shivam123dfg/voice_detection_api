FROM python:3.11-slim

# Install system dependencies (ffmpeg, libsndfile)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libsndfile1-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
# Install CPU-only PyTorch first (much smaller than full CUDA build)
COPY requirements_voice_api.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements_voice_api.txt

# Copy application code
COPY . .

# HF Spaces uses port 7860
EXPOSE 7860

# Pre-download the model at build time so startup is fast.
RUN python -c "\
from transformers import pipeline; \
pipeline('audio-classification', model='MelodyMachine/Deepfake-audio-detection-V2'); \
print('Model cached OK')"

# Start the application
CMD gunicorn --bind 0.0.0.0:${PORT:-7860} --workers 1 --timeout 300 --log-level info voice_detection_api:app