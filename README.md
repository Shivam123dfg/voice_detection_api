---
title: Voice Detection API
emoji: 🎙️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# AI Voice Detection API

A production-ready Flask API that detects whether an audio sample is **AI-generated (deepfake)** or **human** using the [MelodyMachine/Deepfake-audio-detection-V2](https://huggingface.co/MelodyMachine/Deepfake-audio-detection-V2) model (99.73% accuracy). Supports 5 languages: Tamil, English, Hindi, Malayalam, and Telugu.

## 📁 Project Files

| File | Purpose |
|------|---------|
| `voice_detection_api.py` | Main Flask API application |
| `requirements_voice_api.txt` | Python dependencies |
| `Dockerfile` | Docker build for HF Spaces |
| `test_payload.json` | Sample test payload |
| `test cases/` | Base64-encoded test audio files |

## 🚀 Deploy to HuggingFace Spaces

### Step 1: Create a new Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Enter a **Space name** (e.g., `voice-detection-api`)
3. Select **Docker** as the SDK
4. Choose **Public** or **Private**
5. Click **Create Space**

### Step 2: Set Secrets

In your Space → **Settings** → **Variables and secrets**, add:

| Secret | Required | Description |
|--------|----------|-------------|
| `API_SECRET_KEY` | Yes | Your custom API key to protect the endpoint (e.g., `sk_voice_2024_your_random_string`) |

> No HuggingFace token needed — the model is public and runs locally inside the container.

### Step 3: Push code to the Space

```bash
# Clone your new Space
git clone https://huggingface.co/spaces/YOUR_USERNAME/voice-detection-api
cd voice-detection-api

# Copy all project files into the cloned repo
# Then push:
git add .
git commit -m "Initial deployment"
git push
```

The Space will automatically:
1. Build the Docker image
2. Pre-download the deepfake detection model (~95MB)
3. Start the Flask API on port 7860

Build takes ~5-10 minutes on first deploy. Subsequent deploys reuse the cache.

### Step 4: Test the API

**Health Check:**
```bash
curl https://YOUR_USERNAME-voice-detection-api.hf.space/health
```

**Voice Detection:**
```bash
curl -X POST https://YOUR_USERNAME-voice-detection-api.hf.space/api/voice-detection \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_SECRET_KEY" \
  -d @test_payload.json
```

## 🎯 Features

- **Deepfake Detection**: Uses wav2vec2-based model fine-tuned for AI voice detection (99.73% accuracy)
- **Local Inference**: Model runs inside the container — no external API calls, no network errors
- **Multi-language Support**: Tamil, English, Hindi, Malayalam, Telugu
- **Flexible Input**: MP3 and WAV audio via Base64 encoding
- **Secure**: API key authentication on all protected endpoints
- **Rate Limiting**: Built-in request throttling (30 req/min per IP)
- **All-JSON Responses**: Every response (including errors) is JSON

## 📊 API Reference

### `GET /health`

Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "supported_languages": ["Tamil", "English", "Hindi", "Malayalam", "Telugu"],
  "model": "MelodyMachine/Deepfake-audio-detection-V2",
  "inference": "local_pipeline"
}
```

### `POST /api/voice-detection`

Classify audio as AI-generated or human.

**Headers:**
| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `x-api-key` | Your `API_SECRET_KEY` |

**Request Body:**
```json
{
  "language": "English",
  "audioFormat": "wav",
  "audioBase64": "BASE64_ENCODED_AUDIO_DATA"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "language": "English",
  "classification": "HUMAN",
  "confidenceScore": 0.98,
  "explanation": "Top prediction: 'real' (98%)",
  "analysisMethod": "local_pipeline"
}
```

**Error Response (401):**
```json
{
  "status": "error",
  "error_type": "authentication_error",
  "message": "Invalid or missing API key"
}
```

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements_voice_api.txt

# Set environment variable
export API_SECRET_KEY=your_test_key

# Run
python voice_detection_api.py
# API available at http://localhost:5000
```

## 🐳 Run with Docker

Pull and run the pre-built image directly from HuggingFace:

```bash
docker run -it -p 7860:7860 --platform=linux/amd64 \
  -e API_SECRET_KEY="your_secret_key_here" \
  registry.hf.space/asperk123-voice-detection-api:latest
```

The API will be available at `http://localhost:7860`.

**Test locally after Docker install:**
```bash
# Health check
curl http://localhost:7860/health

# Voice detection
curl -X POST http://localhost:7860/api/voice-detection \
  -H "Content-Type: application/json" \
  -H "x-api-key: your_secret_key_here" \
  -d @test_payload.json
```

## 🧪 Live API Test

**Health Check:**
```bash
curl https://asperk123-voice-detection-api.hf.space/health
```

**Voice Detection (with test payload file):**
```bash
curl -X POST https://asperk123-voice-detection-api.hf.space/api/voice-detection \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_SECRET_KEY" \
  -d @test_payload.json
```

**Voice Detection (inline JSON):**
```bash
curl -X POST https://asperk123-voice-detection-api.hf.space/api/voice-detection \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_SECRET_KEY" \
  -d '{
    "language": "English",
    "audioFormat": "wav",
    "audioBase64": "BASE64_ENCODED_AUDIO_DATA"
  }'
```

**Expected Success Response:**
```json
{
  "status": "success",
  "language": "English",
  "classification": "HUMAN",
  "confidenceScore": 1.0,
  "explanation": "Top prediction: 'real' (100%)",
  "analysisMethod": "local_pipeline"
}
```

## 🚨 Security

- Never commit your `API_SECRET_KEY` to the repo
- Set it as a **Secret** in HF Spaces settings
- Use HTTPS (HF Spaces provides this automatically)
- Rate limiting is enabled by default