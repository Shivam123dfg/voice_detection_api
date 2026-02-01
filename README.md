# AI Voice Detection API

This folder contains a complete AI Voice Detection API solution that can detect whether an audio sample (MP3) is AI-generated or human across 5 languages.

## 📁 Folder Contents

### Core Application Files
- `voice_detection_api.py` - Main Flask API application
- `test_voice_api.py` - Test client for the API
- `requirements_voice_api.txt` - Python dependencies

### Configuration Files
- `.env.example` - Environment variables template
- `Dockerfile` - Docker deployment configuration
- `render.yaml` - Render.com deployment config
- `Procfile` - Heroku deployment config
- `app.json` - App metadata for deployment

### Documentation
- `DEPLOYMENT_GUIDE.md` - Complete step-by-step deployment guide
- `README.md` - This file

## 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements_voice_api.txt
   ```

2. **Set Environment Variables**
   ```bash
   copy .env.example .env
   # Edit .env file with your API keys
   ```

3. **Run Locally**
   ```bash
   python voice_detection_api.py
   ```

4. **Test the API**
   ```bash
   python test_voice_api.py
   ```

## 🌐 Deploy to Production

Follow the detailed instructions in `DEPLOYMENT_GUIDE.md` for:
- Render.com (FREE)
- Heroku (FREE) 
- Railway.app (FREE)
- Google Cloud Run (FREE)

## 🎯 Features

✅ Supports 5 languages: Tamil, English, Hindi, Malayalam, Telugu  
✅ MP3 audio input via Base64 encoding  
✅ AI-powered detection using Gemini 2.0-flash-exp  
✅ RESTful API with JSON responses  
✅ API key authentication  
✅ Comprehensive error handling  
✅ Health check endpoint  

## 📊 API Usage

```bash
curl -X POST https://your-deployed-url.com/api/voice-detection \
-H "Content-Type: application/json" \
-H "x-api-key: your_api_key" \
-d '{
    "language": "English",
    "audioFormat": "mp3", 
    "audioBase64": "BASE64_ENCODED_AUDIO_DATA"
}'
```

For complete documentation, see `DEPLOYMENT_GUIDE.md`.