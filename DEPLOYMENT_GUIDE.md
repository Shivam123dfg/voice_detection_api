# Voice Detection API - Complete Deployment Guide

## 🎯 Overview

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

1. **Prepare Your Code**
   ```bash
   # Create a new repository on GitHub
   # Upload all the created files to your repository
   ```

2. **Sign up for Render.com**
   - Go to [render.com](https://render.com)
   - Sign up with your GitHub account

3. **Deploy**
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Choose the repository with your code
   - Configuration:
     - Name: `voice-detection-api`
     - Runtime: `Python 3`
     - Build Command: `pip install -r requirements_voice_api.txt`
     - Start Command: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 voice_detection_api:app`

4. **Set Environment Variables**
   - In Render dashboard, go to your service
   - Go to "Environment" tab
   - Add:
     - `GEMINI_API_KEY`: Your Gemini API key
     - `API_SECRET_KEY`: Your custom API key (e.g., `sk_live_your_secret_key`)

5. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment (5-10 minutes)
   - Your API will be available at: `https://your-app-name.onrender.com`

### Option 2: Deploy to Heroku (FREE tier available)

1. **Install Heroku CLI**
   - Download from [heroku.com/download](https://devcenter.heroku.com/articles/heroku-cli)

2. **Deploy**
   ```bash
   # Login to Heroku
   heroku login
   
   # Create app
   heroku create your-voice-detection-api
   
   # Set environment variables
   heroku config:set GEMINI_API_KEY=your_gemini_api_key
   heroku config:set API_SECRET_KEY=sk_live_your_secret_key
   
   # Deploy
   git init
   git add .
   git commit -m "Initial deployment"
   git push heroku main
   ```

### Option 3: Railway.app (FREE)

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
   # Create virtual environment
   python -m venv venv
   
   # Activate (Windows)
   venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements_voice_api.txt
   ```

2. **Set Environment Variables**
   ```bash
   # Copy environment file
   copy .env.example .env
   
   # Edit .env file with your actual keys
   ```

3. **Run Locally**
   ```bash
   python voice_detection_api.py
   ```

4. **Test Locally**
   ```bash
   python test_voice_api.py
   ```

## 📊 API Endpoints

### POST /api/voice-detection
**Main voice detection endpoint**

**Headers:**
- `Content-Type: application/json`
- `x-api-key: YOUR_API_KEY`

**Request Body:**
```json
{
    "language": "English",
    "audioFormat": "mp3",
    "audioBase64": "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU2LjM2LjEwMAAAAAAA..."
}
```

**Success Response:**
```json
{
    "status": "success",
    "language": "English",
    "classification": "AI_GENERATED",
    "confidenceScore": 0.85,
    "explanation": "Detected unnatural pitch consistency and lack of breathing sounds"
}
```

### GET /health
**Health check endpoint**

**Response:**
```json
{
    "status": "healthy",
    "supported_languages": ["Tamil", "English", "Hindi", "Malayalam", "Telugu"],
    "gemini_available": true
}
```

## 🔒 Security Features

- ✅ API Key authentication
- ✅ Input validation
- ✅ File size limits (10MB)
- ✅ Error handling
- ✅ Request timeout protection

## 🎛️ Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Your Gemini API key | Required |
| `API_SECRET_KEY` | Your API authentication key | Required |
| `PORT` | Port number | 5000 |
| `FLASK_ENV` | Flask environment | production |

### Supported Languages
- Tamil
- English  
- Hindi
- Malayalam
- Telugu

### Supported Audio Format
- MP3 only
- Base64 encoded
- Maximum size: 10MB

## 🔍 Monitoring & Logs

### Check Deployment Status
- **Render.com**: Dashboard → Your Service → Logs
- **Heroku**: `heroku logs --tail`
- **Railway**: Dashboard → Your Project → Deployments

### Health Check
Visit: `https://your-deployed-url.com/health`

## 🛠️ Troubleshooting

### Common Issues

1. **"Gemini client not initialized"**
   - Check your GEMINI_API_KEY environment variable
   - Verify API key is valid in Google AI Studio

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