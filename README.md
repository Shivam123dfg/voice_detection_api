# AI Voice Detection API

This folder contains a complete AI Voice Detection API solution that can detect whether an audio sample (MP3) is AI-generated or human across 5 languages.

## 📁 Folder Contents

### Core Application Files
- `voice_detection_api.py` - Main Flask API application
- `test_voice_api.py` - Test client for the API
- `requirements_voice_api.txt` - Python dependencies

### Configuration Files
- `.env` - Environment variables (local only - not in repo)
- `.gitignore` - Git ignore rules for security
- `Dockerfile` - Docker deployment configuration
- `render.yaml` - Render.com deployment config
- `Procfile` - Heroku deployment config
- `app.json` - App metadata for deployment

### Documentation
- `DEPLOYMENT_GUIDE.md` - Complete step-by-step deployment guide
- `README.md` - This file

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Google AI Studio account for Gemini API key

### 1. **Clone & Install Dependencies**
   ```bash
   git clone https://github.com/Shivam123dfg/voice_detection_api.git
   cd voice_detection_api
   pip install -r requirements_voice_api.txt
   ```

### 2. **Environment Variables Setup**
   Create a `.env` file in the project root with the following variables:
   
   ```bash
   GEMINI_API_KEY=your_gemini_api_key_here
   API_SECRET_KEY=your_custom_secret_key_here
   FLASK_ENV=development
   FLASK_DEBUG=True
   PORT=5000
   SECRET_KEY=your_flask_secret_key_here
   ```

   **How to get API keys:**
   - **GEMINI_API_KEY**: Get from [Google AI Studio](https://ai.google.dev/)
     1. Go to https://ai.google.dev/
     2. Sign in with your Google account
     3. Create a new API key
     4. Copy the key to your `.env` file
   
   - **API_SECRET_KEY**: Create your own secure random string (e.g., `sk_voice_detection_2024_your_random_string`)
   - **SECRET_KEY**: Generate a secure random key for Flask sessions

   **⚠️ Security Note:** Never commit the `.env` file to GitHub! It's already added to `.gitignore`.

### 3. **Run Locally**
   ```bash
   python voice_detection_api.py
   ```
   
   The API will be available at: http://localhost:5000

### 4. **Test the API**
   ```bash
   python test_voice_api.py
   ```

## 🌐 Deploy to Production

**Before deploying, make sure to:**
1. Remove any hardcoded API keys from your code
2. Set environment variables in your deployment platform
3. Never commit `.env` file to GitHub

Follow the detailed instructions in `DEPLOYMENT_GUIDE.md` for:
- **Render.com** (FREE) - Recommended
- Heroku (FREE) 
- Railway.app (FREE)
- Google Cloud Run (FREE)

**For Render deployment:**
1. Push your code to GitHub (without `.env` file)
2. Connect your GitHub repo to Render
3. Set environment variables in Render dashboard:
   - `GEMINI_API_KEY` = your actual Gemini API key
   - `API_SECRET_KEY` = your custom secret key
   - `FLASK_ENV` = production
   - `FLASK_DEBUG` = False

## 🎯 Features

✅ **Multi-language Support**: Tamil, English, Hindi, Malayalam, Telugu  
✅ **Flexible Input**: MP3 audio input via Base64 encoding  
✅ **AI-Powered**: Uses Google's Gemini 2.0-flash-exp model  
✅ **RESTful API**: Clean JSON request/response format  
✅ **Secure Authentication**: API key-based authentication  
✅ **Error Handling**: Comprehensive error responses  
✅ **Health Monitoring**: Built-in health check endpoint  
✅ **Production Ready**: Proper environment variable management  

## 📊 API Usage

### Local Testing
```bash
curl -X POST http://localhost:5000/api/voice-detection \
-H "Content-Type: application/json" \
-H "x-api-key: your_api_secret_key" \
-d '{
    "language": "English",
    "audioFormat": "mp3", 
    "audioBase64": "BASE64_ENCODED_AUDIO_DATA"
}'
```

### Production Usage
```bash
curl -X POST https://your-app-name.onrender.com/api/voice-detection \
-H "Content-Type: application/json" \
-H "x-api-key: your_api_secret_key" \
-d '{
    "language": "English",
    "audioFormat": "mp3", 
    "audioBase64": "BASE64_ENCODED_AUDIO_DATA"
}'
```

### Health Check
```bash
# Check if API is running
curl https://your-app-name.onrender.com/health
```

## 🔧 Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key | `AIzaSyB...` |
| `API_SECRET_KEY` | Yes | Your custom API authentication key | `sk_voice_2024_...` |
| `FLASK_ENV` | No | Flask environment mode | `development` or `production` |
| `FLASK_DEBUG` | No | Enable/disable debug mode | `True` or `False` |
| `PORT` | No | Server port (auto-set by Render) | `5000` |
| `SECRET_KEY` | No | Flask session secret key | Random secure string |

## 🚨 Security Best Practices

- ✅ **Never commit API keys** to GitHub
- ✅ **Use environment variables** for all secrets
- ✅ **Regenerate API keys** if accidentally exposed
- ✅ **Use HTTPS** in production
- ✅ **Validate API key** in all protected endpoints
- ✅ **Monitor API usage** for unusual activity

For complete documentation, see `DEPLOYMENT_GUIDE.md`.