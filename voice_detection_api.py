import os
from dotenv import load_dotenv

# Load environment variables FIRST (before any HF imports)
load_dotenv()

# Disable xet download protocol (causes 403 on some networks)
os.environ["HF_HUB_DISABLE_XET"] = "1"

from flask import Flask, request, jsonify, make_response
import base64
import tempfile
import time
import json
import logging
from functools import wraps
from transformers import pipeline
import librosa
import numpy as np
from pydub import AudioSegment
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
class Config:
    API_SECRET_KEY = os.getenv('API_SECRET_KEY')
    HF_TOKEN = os.getenv('HF_TOKEN')
    SUPPORTED_LANGUAGES = ['Tamil', 'English', 'Hindi', 'Malayalam', 'Telugu']
    MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
    HF_MODEL_ID = "MelodyMachine/Deepfake-audio-detection-V2"

# Validate environment variables at startup
if not Config.API_SECRET_KEY:
    logger.warning("API_SECRET_KEY is not set. Protected endpoints will reject all requests until it is configured.")

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
# LOAD MODEL LOCALLY AT STARTUP
# ---------------------------------------------------------------------------
logger.info(f"Loading model locally: {Config.HF_MODEL_ID}...")
try:
    _pipeline_kwargs = {
        "task": "audio-classification",
        "model": Config.HF_MODEL_ID,
        "dtype": torch.float16,
        "device": "cpu",
    }
    if Config.HF_TOKEN:
        _pipeline_kwargs["token"] = Config.HF_TOKEN
    audio_classifier = pipeline(**_pipeline_kwargs)
    logger.info(f"Model loaded successfully: {Config.HF_MODEL_ID}")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    audio_classifier = None

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
    ALLOWED_FORMATS = ('mp3', 'wav')
    audio_format = data['audioFormat']
    if not isinstance(audio_format, str):
        errors.append("'audioFormat' must be a string")
    elif audio_format.lower() not in ALLOWED_FORMATS:
        errors.append(f"Unsupported audioFormat '{audio_format}'. Allowed: {ALLOWED_FORMATS}")

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
    def _get_tempo(y, sr):
        """Get tempo, compatible with both old and new librosa versions."""
        try:
            # librosa >= 0.10.2
            tempo = librosa.feature.rhythm.tempo(y=y, sr=sr)
        except AttributeError:
            # librosa < 0.10.2
            tempo = librosa.beat.tempo(y=y, sr=sr)
        return float(tempo[0]) if len(tempo) > 0 else 0.0

    @staticmethod
    def extract_audio_features(audio_bytes, audio_format='mp3'):
        """Extract audio features for analysis."""
        temp_path = None
        wav_path = None
        try:
            suffix = f'.{audio_format}'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                temp_path = tmp.name

            if audio_format == 'wav':
                wav_path = temp_path          # already WAV, use directly
            else:
                audio = AudioSegment.from_mp3(temp_path)
                wav_path = temp_path.replace(suffix, '.wav')
                audio.export(wav_path, format="wav")

            y, sr = librosa.load(wav_path, sr=None)

            features = {
                'duration': len(y) / sr,
                'sample_rate': sr,
                'rms_energy': float(np.mean(librosa.feature.rms(y=y))),
                'spectral_centroid': float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
                'zero_crossing_rate': float(np.mean(librosa.feature.zero_crossing_rate(y))),
                'mfcc_mean': [float(x) for x in np.mean(librosa.feature.mfcc(y=y, sr=sr), axis=1)[:13]],
                'tempo': float(AudioProcessor._get_tempo(y, sr)),
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
# VOICE DETECTOR  (local transformers pipeline)
# ---------------------------------------------------------------------------
class VoiceDetector:
    def __init__(self):
        self.classifier = audio_classifier

    def analyze_voice(self, audio_bytes, audio_format, language):
        """Analyse voice using locally loaded model."""
        try:
            return self._classify_audio(audio_bytes, audio_format)
        except Exception as e:
            logger.error(f"Model inference failed: {type(e).__name__}: {e!r}")
            return self._fallback_analysis(audio_bytes, audio_format, language)

    def _classify_audio(self, audio_bytes, audio_format):
        """Run audio classification using local transformers pipeline."""
        if self.classifier is None:
            raise RuntimeError("Model not loaded")

        # Save audio bytes to a temp file for the pipeline
        temp_path = None
        try:
            suffix = f'.{audio_format}'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                temp_path = tmp.name

            results = self.classifier(temp_path)

            if results and len(results) > 0:
                top = max(results, key=lambda x: x['score'])
                label = top['label'].lower()
                score = float(top['score'])

                if label == 'fake':
                    classification = 'AI_GENERATED'
                elif label == 'real':
                    classification = 'HUMAN'
                else:
                    logger.warning(f"Unexpected model label: '{top['label']}'")
                    classification = 'HUMAN'

                return {
                    "classification": classification,
                    "confidence_score": round(score, 2),
                    "explanation": (
                        f"Model classified as '{top['label']}' "
                        f"with {score:.0%} confidence"
                    ),
                    "analysis_method": "local_model",
                }

            raise ValueError("No results from model")
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def _fallback_analysis(self, audio_bytes, audio_format, language):
        """Heuristic fallback when model inference fails."""
        try:
            audio_features = AudioProcessor.extract_audio_features(
                audio_bytes, audio_format
            )
        except Exception:
            return {
                "classification": "HUMAN",
                "confidence_score": 0.50,
                "explanation": "Unable to analyze audio. Default classification applied.",
                "analysis_method": "default_fallback",
            }

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
                "analysis_method": "heuristic_fallback",
            }
        return {
            "classification": "HUMAN",
            "confidence_score": 0.60,
            "explanation": "Audio characteristics suggest natural human speech patterns (heuristic fallback).",
            "analysis_method": "heuristic_fallback",
        }

# ---------------------------------------------------------------------------
# INITIALISE
# ---------------------------------------------------------------------------
voice_detector = VoiceDetector()

# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------
@app.route('/api/voice-detection', methods=['POST'])
@limiter.limit("30 per minute")
@require_api_key
def voice_detection():
    """Main voice detection endpoint."""
    try:
        logger.info("="*60)
        logger.info("STEP 1: Received voice detection request")

        # --- Content-Type check ---
        if not request.is_json:
            logger.warning("STEP 1 FAILED: Content-Type is not JSON")
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": "Content-Type must be application/json",
            }), 400

        data = request.get_json(silent=True)
        logger.info("STEP 2: JSON payload parsed successfully")

        # --- Payload validation ---
        validation_errors, cleaned = validate_request_payload(data)
        if validation_errors:
            logger.warning(f"STEP 2 FAILED: Validation errors: {validation_errors}")
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": "; ".join(validation_errors),
            }), 400

        language = cleaned['language']
        audio_base64 = cleaned['audioBase64']
        audio_format = cleaned['audioFormat']
        logger.info(f"STEP 3: Validated - language={language}, format={audio_format}, base64_len={len(audio_base64)}")

        # --- Decode audio ---
        try:
            audio_bytes = AudioProcessor.decode_base64_audio(audio_base64)
            logger.info(f"STEP 4: Audio decoded - {len(audio_bytes)} bytes ({len(audio_bytes)//1024} KB)")
        except ValueError as e:
            logger.error(f"STEP 4 FAILED: Base64 decode error: {e}")
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": str(e),
            }), 400

        # --- Size check ---
        if len(audio_bytes) > Config.MAX_AUDIO_SIZE:
            logger.warning(f"STEP 4 FAILED: Audio too large ({len(audio_bytes)} bytes)")
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": f"Audio file too large. Maximum size: {Config.MAX_AUDIO_SIZE // (1024*1024)}MB",
            }), 400

        # --- Voice analysis via local model ---
        logger.info("STEP 5: Running local model inference...")
        _t0 = time.monotonic()
        analysis_result = voice_detector.analyze_voice(audio_bytes, audio_format, language)
        _elapsed = time.monotonic() - _t0
        logger.info(f"STEP 5: Analysis complete in {_elapsed:.1f}s - method={analysis_result.get('analysis_method')}, "
                    f"classification={analysis_result['classification']}, "
                    f"confidence={analysis_result['confidence_score']:.2f}")
        logger.info(f"STEP 5: Explanation: {analysis_result.get('explanation', 'N/A')}")
        logger.info("="*60)

        return jsonify({
            "status": "success",
            "language": language,
            "classification": analysis_result["classification"],
            "confidenceScore": round(analysis_result["confidence_score"], 2),
            "explanation": analysis_result["explanation"],
            "analysisMethod": analysis_result.get("analysis_method", "unknown"),
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
        "model_loaded": audio_classifier is not None,
        "model": Config.HF_MODEL_ID,
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
    app.run(host='0.0.0.0', port=port, debug=True)
