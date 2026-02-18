from flask import Flask, request, jsonify, make_response
import base64
import os
import tempfile
import json
import time
from google import genai
import logging
from functools import wraps
import librosa
import numpy as np
from pydub import AudioSegment
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
class Config:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    API_SECRET_KEY = os.getenv('API_SECRET_KEY')
    SUPPORTED_LANGUAGES = ['Tamil', 'English', 'Hindi', 'Malayalam', 'Telugu']
    MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
    GEMINI_MAX_RETRIES = 3
    GEMINI_RETRY_DELAY = 2  # seconds (initial backoff)

# Validate environment variables at startup
if not Config.GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")
if not Config.API_SECRET_KEY:
    raise ValueError("API_SECRET_KEY environment variable is required")

# ---------------------------------------------------------------------------
# FLASK-LIMITER  –  rate-limit responses are ALWAYS JSON
# ---------------------------------------------------------------------------
def _rate_limit_exceeded_handler(e):
    """Return a proper JSON 429 response instead of plain text."""
    return make_response(
        jsonify({
            "status": "error",
            "error_type": "rate_limit",
            "message": "Too Many Requests. Please wait and try again.",
        }),
        429,
    )

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    on_breach=_rate_limit_exceeded_handler,
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# ENSURE *EVERY* RESPONSE IS JSON  (catches any unexpected non-JSON leaks)
# ---------------------------------------------------------------------------
@app.after_request
def force_json_content_type(response):
    """Guarantee Content-Type: application/json on every response."""
    if response.content_type and 'application/json' not in response.content_type:
        try:
            json.loads(response.get_data(as_text=True))
            response.content_type = 'application/json'
        except (json.JSONDecodeError, Exception):
            original_text = response.get_data(as_text=True)
            status_code = response.status_code
            error_type = "server_error"
            if status_code == 429:
                error_type = "rate_limit"
            elif status_code == 404:
                error_type = "not_found"
            elif status_code == 401:
                error_type = "authentication_error"
            elif status_code == 400:
                error_type = "validation_error"
            wrapped = json.dumps({
                "status": "error",
                "error_type": error_type,
                "message": original_text.strip() or "An unexpected error occurred",
            })
            response.set_data(wrapped)
            response.content_type = 'application/json'
    return response

# ---------------------------------------------------------------------------
# GEMINI CLIENT INITIALISATION
# ---------------------------------------------------------------------------
try:
    gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
    logger.info("Gemini client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    gemini_client = None

# ---------------------------------------------------------------------------
# AUTHENTICATION DECORATOR
# ---------------------------------------------------------------------------
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('x-api-key')
        if not api_key or api_key != Config.API_SECRET_KEY:
            return jsonify({
                "status": "error",
                "error_type": "authentication_error",
                "message": "Invalid or missing API key",
            }), 401
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------------------------------------------
# REQUEST VALIDATION
# ---------------------------------------------------------------------------
def validate_request_payload(data):
    """Validate the incoming JSON payload. Returns (errors_list, cleaned_data)."""
    errors = []

    if data is None:
        return ["Request body must be valid JSON"], None

    required_fields = ['language', 'audioFormat', 'audioBase64']
    for field in required_fields:
        if field not in data or data[field] is None:
            errors.append(f"Missing required field: '{field}'")

    if errors:
        return errors, None

    # --- language ---
    language = data['language']
    if not isinstance(language, str):
        errors.append("'language' must be a string")
    elif language not in Config.SUPPORTED_LANGUAGES:
        errors.append(
            f"Unsupported language '{language}'. Supported: {Config.SUPPORTED_LANGUAGES}"
        )

    # --- audioFormat ---
    audio_format = data['audioFormat']
    if not isinstance(audio_format, str):
        errors.append("'audioFormat' must be a string")
    elif audio_format.lower() != 'mp3':
        errors.append("Only 'mp3' audioFormat is currently supported")

    # --- audioBase64 ---
    audio_base64 = data['audioBase64']
    if not isinstance(audio_base64, str) or len(audio_base64.strip()) == 0:
        errors.append("'audioBase64' must be a non-empty string")

    if errors:
        return errors, None

    return [], {
        "language": language,
        "audioFormat": audio_format.lower(),
        "audioBase64": audio_base64.strip(),
    }

# ---------------------------------------------------------------------------
# AUDIO PROCESSING
# ---------------------------------------------------------------------------
class AudioProcessor:
    @staticmethod
    def decode_base64_audio(base64_string):
        """Decode base64 audio to bytes."""
        try:
            audio_bytes = base64.b64decode(base64_string)
            return audio_bytes
        except Exception as e:
            logger.error(f"Failed to decode base64 audio: {e}")
            raise ValueError("Invalid base64 audio data")

    @staticmethod
    def extract_audio_features(audio_bytes):
        """Extract audio features for analysis."""
        temp_path = None
        wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(audio_bytes)
                temp_path = tmp.name

            audio = AudioSegment.from_mp3(temp_path)
            wav_path = temp_path.replace('.mp3', '.wav')
            audio.export(wav_path, format="wav")

            y, sr = librosa.load(wav_path, sr=None)

            features = {
                'duration': len(y) / sr,
                'sample_rate': sr,
                'rms_energy': float(np.mean(librosa.feature.rms(y=y))),
                'spectral_centroid': float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
                'zero_crossing_rate': float(np.mean(librosa.feature.zero_crossing_rate(y))),
                'mfcc_mean': [float(x) for x in np.mean(librosa.feature.mfcc(y=y, sr=sr), axis=1)[:13]],
                'tempo': float(librosa.beat.tempo(y=y, sr=sr)[0])
                         if len(librosa.beat.tempo(y=y, sr=sr)) > 0 else 0.0,
            }
            return features

        except Exception as e:
            logger.error(f"Failed to extract audio features: {e}")
            raise ValueError("Failed to process audio file")
        finally:
            for p in (temp_path, wav_path):
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

# ---------------------------------------------------------------------------
# VOICE DETECTOR  (with Gemini retry / exponential back-off)
# ---------------------------------------------------------------------------
class VoiceDetector:
    def __init__(self, client):
        self.client = client

    def analyze_voice(self, audio_features, language):
        """Analyse voice with retries on Gemini rate-limit / transient errors."""
        last_error = None

        for attempt in range(1, Config.GEMINI_MAX_RETRIES + 1):
            try:
                return self._call_gemini(audio_features, language)
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                is_rate_limit = any(
                    kw in error_msg for kw in ['429', 'rate', 'quota', 'resource_exhausted']
                )
                if is_rate_limit and attempt < Config.GEMINI_MAX_RETRIES:
                    wait = Config.GEMINI_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"Gemini rate-limited (attempt {attempt}/{Config.GEMINI_MAX_RETRIES}). "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                elif not is_rate_limit:
                    break

        logger.error(f"All Gemini attempts failed: {last_error}")
        return self._fallback_analysis(audio_features, language)

    def _call_gemini(self, audio_features, language):
        """Single Gemini API call."""
        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        analysis_prompt = f"""You are an expert voice analyst specializing in detecting AI-generated vs human voices in {language} language.

Analyze the following audio features and determine if this voice sample is AI-generated or human:

Audio Features:
- Duration: {audio_features['duration']:.2f} seconds
- Sample Rate: {audio_features['sample_rate']} Hz
- RMS Energy: {audio_features['rms_energy']:.6f}
- Spectral Centroid: {audio_features['spectral_centroid']:.2f}
- Zero Crossing Rate: {audio_features['zero_crossing_rate']:.6f}
- MFCC Features: {audio_features['mfcc_mean'][:5]}
- Tempo: {audio_features['tempo']:.2f} BPM

Language: {language}

Based on these audio characteristics, analyze:
1. Naturalness of speech patterns
2. Pitch consistency and variation
3. Breathing patterns and pauses
4. Spectral characteristics typical of human vs AI voices
5. Language-specific phonetic patterns

Consider that AI voices often have:
- Unnatural pitch consistency
- Lack of subtle breathing sounds
- Robotic speech patterns
- Unusual spectral characteristics
- Perfect pronunciation without natural speech variations

Human voices typically have:
- Natural pitch variations
- Subtle background noise and breathing
- Slight pronunciation inconsistencies
- Natural pauses and speech rhythm
- Emotional undertones

Respond ONLY with a single valid JSON object (no markdown, no extra text):
{{"status":"success","language":"{language}","classification":"AI_GENERATED or HUMAN","confidence_score":0.XX,"explanation":"Brief technical explanation"}}"""

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=analysis_prompt,
        )

        response_text = response.text.strip()

        # Strip markdown fences if present
        if '```json' in response_text:
            response_text = response_text.split('```json', 1)[1]
            response_text = response_text.split('```', 1)[0]
        elif '```' in response_text:
            response_text = response_text.split('```', 1)[1]
            response_text = response_text.split('```', 1)[0]

        if '{' in response_text:
            response_text = response_text[response_text.find('{'):response_text.rfind('}') + 1]

        result = json.loads(response_text)

        if 'classification' not in result or 'confidence_score' not in result:
            raise ValueError("Gemini returned invalid JSON structure")

        if result['classification'] not in ('AI_GENERATED', 'HUMAN'):
            result['classification'] = 'HUMAN'

        result['confidence_score'] = max(0.0, min(1.0, float(result['confidence_score'])))
        return result

    def _fallback_analysis(self, audio_features, language):
        """Heuristic fallback when Gemini is unavailable."""
        ai_indicators = 0
        if audio_features['rms_energy'] > 0.1:
            ai_indicators += 1
        if audio_features['spectral_centroid'] > 3000:
            ai_indicators += 1
        if audio_features['zero_crossing_rate'] < 0.05:
            ai_indicators += 1

        if ai_indicators >= 2:
            return {
                "classification": "AI_GENERATED",
                "confidence_score": 0.70,
                "explanation": "Detected consistent audio patterns typical of AI-generated speech (heuristic fallback).",
            }
        return {
            "classification": "HUMAN",
            "confidence_score": 0.60,
            "explanation": "Audio characteristics suggest natural human speech patterns (heuristic fallback).",
        }

# ---------------------------------------------------------------------------
# INITIALISE
# ---------------------------------------------------------------------------
voice_detector = VoiceDetector(gemini_client)

# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------
@app.route('/api/voice-detection', methods=['POST'])
@limiter.limit("30 per minute")
@require_api_key
def voice_detection():
    """Main voice detection endpoint."""
    try:
        # --- Content-Type check ---
        if not request.is_json:
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": "Content-Type must be application/json",
            }), 400

        data = request.get_json(silent=True)

        # --- Payload validation ---
        validation_errors, cleaned = validate_request_payload(data)
        if validation_errors:
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": "; ".join(validation_errors),
            }), 400

        language = cleaned['language']
        audio_base64 = cleaned['audioBase64']

        # --- Decode audio ---
        try:
            audio_bytes = AudioProcessor.decode_base64_audio(audio_base64)
        except ValueError as e:
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": str(e),
            }), 400

        # --- Size check ---
        if len(audio_bytes) > Config.MAX_AUDIO_SIZE:
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": f"Audio file too large. Maximum size: {Config.MAX_AUDIO_SIZE // (1024*1024)}MB",
            }), 400

        # --- Feature extraction ---
        try:
            audio_features = AudioProcessor.extract_audio_features(audio_bytes)
        except ValueError as e:
            return jsonify({
                "status": "error",
                "error_type": "processing_error",
                "message": str(e),
            }), 422

        # --- Voice analysis ---
        analysis_result = voice_detector.analyze_voice(audio_features, language)

        return jsonify({
            "status": "success",
            "language": language,
            "classification": analysis_result["classification"],
            "confidenceScore": round(analysis_result["confidence_score"], 2),
            "explanation": analysis_result["explanation"],
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error in voice_detection: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "error_type": "server_error",
            "message": "Internal server error. Please try again later.",
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "supported_languages": Config.SUPPORTED_LANGUAGES,
        "gemini_available": gemini_client is not None,
    }), 200

# ---------------------------------------------------------------------------
# GLOBAL ERROR HANDLERS  –  ALWAYS return JSON
# ---------------------------------------------------------------------------
@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        "status": "error",
        "error_type": "bad_request",
        "message": str(error.description) if hasattr(error, 'description') else "Bad request",
    }), 400

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({
        "status": "error",
        "error_type": "authentication_error",
        "message": "Unauthorized. Provide a valid x-api-key header.",
    }), 401

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "error_type": "not_found",
        "message": "Endpoint not found",
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "status": "error",
        "error_type": "method_not_allowed",
        "message": "HTTP method not allowed for this endpoint",
    }), 405

@app.errorhandler(429)
def too_many_requests(error):
    return jsonify({
        "status": "error",
        "error_type": "rate_limit",
        "message": "Too Many Requests. Please wait and try again.",
    }), 429

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "status": "error",
        "error_type": "server_error",
        "message": "Internal server error",
    }), 500

@app.errorhandler(Exception)
def handle_any_exception(error):
    """Catch-all so nothing ever returns plain text."""
    logger.error(f"Unhandled exception: {error}", exc_info=True)
    return jsonify({
        "status": "error",
        "error_type": "server_error",
        "message": "An unexpected error occurred. Please try again.",
    }), 500

# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
