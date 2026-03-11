# Voice Detection API - Complete Deployment Guide

## Overview

This guide will help you deploy the AI Voice Detection API that can detect whether an audio sample (MP3) is AI-generated or human across 5 languages: Tamil, English, Hindi, Malayalam, and Telugu.

## Project Files

| File | Description |
|------|-------------|
| `voice_detection_api.py` | Main Flask API application |
| `requirements_voice_api.txt` | Python dependencies |
| `packages.txt` | System-level dependencies (ffmpeg, libsndfile) |
| `Dockerfile` | Docker image definition for deployment |
| `render.yaml` | Render.com deployment config (Docker runtime) |
| `test_payload.json` | Sample JSON payload for testing |
| `.env.example` | Environment variables template |

## Key Features

- **Docker-based deployment** — system dependencies (ffmpeg, libsndfile) are installed reliably inside the Docker image, avoiding read-only filesystem issues on platforms like Render.
- **Rate limiting** — 60 requests/min globally, 30 requests/min on the detection endpoint (Flask-Limiter).
- **Retry with exponential back-off** — automatic retries (up to 3) on GitHub Models rate-limit or transient errors.
- **Heuristic fallback** — if the LLM is unavailable, a feature-based heuristic still returns a classification.
- **All-JSON responses** — every response (including errors, 404s, and rate-limit breaches) is guaranteed JSON.

---

## Step-by-Step Deployment

### Option 1: Deploy to Render.com (FREE - Recommended)

> **Important:** This project uses a **Docker** runtime. Render auto-detects the `Dockerfile` in the repo root.

1. **Push your code to GitHub**
   ```bash
   git add .
   git commit -m "Deploy voice detection API"
   git push origin main
   ```

2. **Sign up for Render.com**
   - Go to [render.com](https://render.com)
   - Sign up with your GitHub account

3. **Create the service**
   - Click **New** → **Web Service**
   - Connect your GitHub repository
   - Render will **auto-detect the Dockerfile** and select **Docker** as the runtime
   - Configuration:
     - **Name:** `voice-detection-api`
     - **Runtime:** Docker *(auto-detected)*
     - **Plan:** Free
   - Leave **Build Command** and **Start Command** blank — the Dockerfile handles both

4. **Set Environment Variables**
   - In Render dashboard → your service → **Environment** tab
   - Add:
     - `GITHUB_TOKEN` — Your GitHub Personal Access Token (with GitHub Models access)
     - `API_SECRET_KEY` — Your custom API key (e.g., `sk_live_your_secret_key`)

5. **Deploy**
   - Click **Create Web Service**
   - Wait for the Docker image to build and deploy (5–10 minutes)
   - Your API will be available at: `https://your-app-name.onrender.com`

> **Troubleshooting Render:** If your existing service was created with Python runtime and you can't switch to Docker in the UI, **delete the service and recreate it**. Render will detect the Dockerfile on fresh creation.

### Option 2: Deploy to Heroku

1. **Install Heroku CLI** — [heroku.com/download](https://devcenter.heroku.com/articles/heroku-cli)

2. **Deploy**
   ```bash
   heroku login
   heroku create your-voice-detection-api

   # Set the stack to container (Docker)
   heroku stack:set container

   heroku config:set GITHUB_TOKEN=your_github_token
   heroku config:set API_SECRET_KEY=sk_live_your_secret_key

   git push heroku main
   ```

### Option 3: Railway.app

1. Sign up at [railway.app](https://railway.app)
2. Click **Deploy from GitHub repo** and select your repository
3. Railway auto-detects the Dockerfile
4. Set environment variables (`GITHUB_TOKEN`, `API_SECRET_KEY`) in the Railway dashboard
5. Deploy automatically

### Option 4: Google Cloud Run

```bash
# Build Docker image
docker build -t voice-detection-api .

# Tag for Google Cloud
docker tag voice-detection-api gcr.io/YOUR_PROJECT_ID/voice-detection-api

# Push to Google Container Registry
docker push gcr.io/YOUR_PROJECT_ID/voice-detection-api

# Deploy to Cloud Run
gcloud run deploy voice-detection-api \
  --image gcr.io/YOUR_PROJECT_ID/voice-detection-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GITHUB_TOKEN=your_token,API_SECRET_KEY=your_key
```

---

## Local Development & Testing

1. **Setup Environment**
   ```bash
   python -m venv .venv

   # Activate (Windows)
   .venv\Scripts\activate

   # Activate (macOS/Linux)
   source .venv/bin/activate

   pip install -r requirements_voice_api.txt
   ```

2. **Set Environment Variables**
   ```bash
   # Copy the template
   copy .env.example .env      # Windows
   cp .env.example .env        # macOS/Linux

   # Edit .env with your actual keys
   ```

3. **Run Locally**
   ```bash
   python voice_detection_api.py
   ```
   The server starts on `http://localhost:5000`.

4. **Run with Docker Locally** *(optional)*
   ```bash
   docker build -t voice-detection-api .
   docker run -p 5000:10000 \
     -e GITHUB_TOKEN=your_token \
     -e API_SECRET_KEY=your_key \
     voice-detection-api
   ```

---

## API Endpoints

### POST /api/voice-detection

**Main voice detection endpoint** — rate-limited to 30 requests/min per IP.

**Headers:**
| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `x-api-key` | Your `API_SECRET_KEY` |

**Request Body:**
```json
{
    "language": "English",
    "audioFormat": "mp3",
    "audioBase64": "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU2LjM2LjEwMAAAAAAA..."
}
```

**Success Response (200):**
```json
{
    "status": "success",
    "language": "English",
    "classification": "AI_GENERATED",
    "confidenceScore": 0.85,
    "explanation": "Detected unnatural pitch consistency and lack of breathing sounds"
}
```

**Error Response (4xx/5xx):**
```json
{
    "status": "error",
    "error_type": "validation_error",
    "message": "Description of the error"
}
```

Error types: `validation_error`, `authentication_error`, `processing_error`, `rate_limit`, `not_found`, `method_not_allowed`, `server_error`.

### GET /health

**Health check endpoint** — no authentication required.

**Response:**
```json
{
    "status": "healthy",
    "supported_languages": ["Tamil", "English", "Hindi", "Malayalam", "Telugu"],
    "github_models_available": true,
    "model": "gpt-4o"
}
```

---

## Testing Your Deployed API

### Using cURL

```bash
curl -X POST https://your-deployed-url.com/api/voice-detection \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk_live_your_secret_key" \
  -d '{
    "language": "English",
    "audioFormat": "mp3",
    "audioBase64": "BASE64_ENCODED_AUDIO_DATA"
  }'
```

### Using Python

```python
import requests
import base64

# Encode your audio file
with open("sample.mp3", "rb") as f:
    audio_base64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "https://your-deployed-url.com/api/voice-detection",
    headers={
        "Content-Type": "application/json",
        "x-api-key": "sk_live_your_secret_key",
    },
    json={
        "language": "English",
        "audioFormat": "mp3",
        "audioBase64": audio_base64,
    },
)

print(response.json())
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub Personal Access Token (GitHub Models) | **Required** |
| `API_SECRET_KEY` | API authentication key for `x-api-key` header | **Required** |
| `PORT` | Port number | `5000` (local) / `10000` (Docker) |

### Supported Languages

Tamil, English, Hindi, Malayalam, Telugu

### Audio Constraints

- Format: MP3 only
- Encoding: Base64
- Max size: 10 MB

### Rate Limits

| Scope | Limit |
|-------|-------|
| Global (all endpoints) | 60 requests/min per IP |
| `/api/voice-detection` | 30 requests/min per IP |

---

## Security Features

- API Key authentication (`x-api-key` header)
- Input validation on all fields
- File size limits (10 MB)
- Rate limiting (Flask-Limiter)
- All responses guaranteed JSON (no plain-text leaks)
- Comprehensive error handling with typed errors

---

## Monitoring & Logs

### Health Check
```
GET https://your-deployed-url.com/health
```

### Platform Logs
- **Render:** Dashboard → Your Service → Logs
- **Heroku:** `heroku logs --tail`
- **Railway:** Dashboard → Your Project → Deployments

---

## Troubleshooting

| Symptom | Cause & Fix |
|---------|-------------|
| **"GitHub Models client not initialized"** | `GITHUB_TOKEN` is missing or invalid. Verify at https://github.com/settings/tokens |
| **"Invalid or missing API key"** | `x-api-key` header doesn't match `API_SECRET_KEY` env var |
| **"Failed to process audio file"** | Invalid MP3, bad Base64, or file > 10 MB |
| **429 Too Many Requests** | Rate limit hit — wait and retry |
| **Build fails with "Read-only file system"** | Service is using Python runtime instead of Docker. Delete and recreate the service so Render detects the Dockerfile. |
| **Deployment timeout** | Free-tier cold starts can take 30–60 s. The Docker image build may take ~5 min on first deploy. |
