# Voice Detection API - Complete Deployment Guide

## Overview

This guide will help you deploy the AI Voice Detection API that can detect whether an audio sample (MP3) is AI-generated or human across 5 languages: Tamil, English, Hindi, Malayalam, and Telugu.

## 📁 Files Created

- `voice_detection_api.py` - Main Flask API application
- `requirements_voice_api.txt` - Python dependencies
- `test_voice_api.py` - Test client for the API
- `.env.example` - Environment variables template
- `Dockerfile` - Docker configuration
- `render.yaml` - Render.com deployment config
- `Procfile` - Heroku deployment config
- `app.json` - App metadata

## 🚀 Step-by-Step Deployment

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
     - `HF_API_TOKEN`: Your HuggingFace API token (from https://huggingface.co/settings/tokens)
     - `API_SECRET_KEY`: Your custom API key (e.g., `sk_live_your_secret_key`)

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
   
   # Set environment variables
   heroku config:set HF_API_TOKEN=your_huggingface_token
   heroku config:set API_SECRET_KEY=sk_live_your_secret_key

   git push heroku main
   ```

### Option 3: Railway.app

1. **Go to Railway.app**
   - Sign up at [railway.app](https://railway.app)

2. **Deploy from GitHub**
   - Click "Deploy from GitHub repo"
   - Select your repository
   - Set environment variables in Railway dashboard
   - Deploy automatically

### Option 4: Google Cloud Run (FREE tier)

1. **Build and deploy with Docker**
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
     --allow-unauthenticated
   ```

## 🧪 Testing Your Deployed API

### Using the Test Script

1. **Update the test script**
   ```python
   # In test_voice_api.py, change the URL
   client = VoiceDetectionClient("https://your-deployed-url.com")
   ```

2. **Run tests**
   ```bash
   python test_voice_api.py
   ```

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

### Using Python Requests

```python
import requests
import base64

# Encode your audio file
with open("sample.mp3", "rb") as f:
    audio_base64 = base64.b64encode(f.read()).decode()

# Make request
response = requests.post(
    "https://your-deployed-url.com/api/voice-detection",
    headers={
        "Content-Type": "application/json",
        "x-api-key": "sk_live_your_secret_key"
    },
    json={
        "language": "English",
        "audioFormat": "mp3",
        "audioBase64": audio_base64
    }
)

print(response.json())
```

## 🔧 Local Development & Testing

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
   python test_voice_api.py
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
    "huggingface_configured": true,
    "model": "MelodyMachine/Deepfake-audio-detection-V2"
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
| `HF_API_TOKEN` | Your HuggingFace API token | Required |
| `API_SECRET_KEY` | Your API authentication key | Required |
| `PORT` | Port number | 5000 |
| `FLASK_ENV` | Flask environment | production |

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
Visit: `https://your-deployed-url.com/health`

## 🛠️ Troubleshooting

### Common Issues

1. **"HuggingFace API token not configured"**
   - Check your HF_API_TOKEN environment variable
   - Verify token is valid at https://huggingface.co/settings/tokens

2. **"Invalid API key"**
   - Check x-api-key header in your requests
   - Verify API_SECRET_KEY environment variable

3. **"Audio processing failed"**
   - Ensure audio is valid MP3 format
   - Check base64 encoding is correct
   - Verify file size is under 10MB

4. **Deployment failed**
   - Check all required files are uploaded
   - Verify requirements.txt is correct
   - Check environment variables are set

### Getting Help

1. Check the `/health` endpoint
2. Review application logs
3. Test with the provided test script
4. Verify all environment variables are set correctly

## 🎉 Success!

Once deployed, your API will be available at your chosen platform's URL. You can now:

1. Accept MP3 audio files in Base64 format
2. Detect AI-generated vs Human voices
3. Support 5 languages (Tamil, English, Hindi, Malayalam, Telugu)
4. Return JSON responses with classification and confidence scores
5. Handle authentication with API keys

Your free public URL endpoint is now ready for production use!

## 💡 Next Steps

1. **Monitor Usage**: Set up monitoring for API calls
2. **Improve Accuracy**: Fine-tune the detection algorithm based on real data
3. **Scale**: Upgrade to paid plans if you need higher limits
4. **Security**: Implement rate limiting for production use
5. **Documentation**: Create API documentation for users