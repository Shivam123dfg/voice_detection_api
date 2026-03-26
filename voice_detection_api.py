from flask import Flask, request, jsonify, make_response
import base64
import io
import os
import tempfile
import json
import time
import logging
from functools import wraps
from huggingface_hub import InferenceClient
import librosa
import numpy as np
from pydub import AudioSegment
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
class Config:
    HF_API_TOKEN = os.getenv('HF_API_TOKEN')
    API_SECRET_KEY = os.getenv('API_SECRET_KEY')
    SUPPORTED_LANGUAGES = ['Tamil', 'English', 'Hindi', 'Malayalam', 'Telugu']
    MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
    HF_MAX_RETRIES = 3
    HF_RETRY_DELAY = 2  # seconds (initial backoff)
    HF_MODEL_ID = "MelodyMachine/Deepfake-audio-detection-V2"

# Validate environment variables at startup
if not Config.HF_API_TOKEN:
    logger.warning("HF_API_TOKEN is not set. Voice detection will use heuristic fallback only.")
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
# HUGGINGFACE MODEL CONFIGURATION
# ---------------------------------------------------------------------------
if Config.HF_API_TOKEN:
    logger.info(f"HuggingFace configured: model={Config.HF_MODEL_ID}")
else:
    logger.warning("HuggingFace API token not set, will use heuristic fallback")

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
    def compress_audio_if_needed(audio_bytes, audio_format='mp3', target_base64_kb=10):
        """Compress audio so its base64 encoding stays within target_base64_kb."""
        base64_size_kb = len(base64.b64encode(audio_bytes)) / 1024

        if base64_size_kb <= target_base64_kb:
            logger.info(f"Audio base64 size is {base64_size_kb:.1f} KB — within {target_base64_kb} KB limit, no compression needed")
            return audio_bytes, audio_format

        logger.info(f"Audio base64 size is {base64_size_kb:.1f} KB — exceeds {target_base64_kb} KB limit. Compressing...")

        temp_path = None
        try:
            suffix = f'.{audio_format}'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                temp_path = tmp.name

            # Auto-detect format: try declared format first, then fallback
            try:
                if audio_format == 'wav':
                    audio = AudioSegment.from_wav(temp_path)
                else:
                    audio = AudioSegment.from_mp3(temp_path)
            except Exception:
                logger.warning(
                    f"Could not load as '{audio_format}', "
                    f"trying auto-detect..."
                )
                audio = AudioSegment.from_file(temp_path)

            # Convert to mono to reduce size
            audio = audio.set_channels(1)

            # Try progressively lower sample rates and bitrates
            sample_rates = [16000, 12000, 8000]
            bitrates = ['32k', '24k', '16k']

            for sr in sample_rates:
                resampled = audio.set_frame_rate(sr)
                for br in bitrates:
                    buf = io.BytesIO()
                    resampled.export(buf, format='mp3', bitrate=br)
                    compressed = buf.getvalue()
                    compressed_b64_kb = len(base64.b64encode(compressed)) / 1024
                    if compressed_b64_kb <= target_base64_kb:
                        logger.info(
                            f"Compressed to {compressed_b64_kb:.1f} KB base64 "
                            f"(sample_rate={sr}, bitrate={br})"
                        )
                        return compressed, 'mp3'

            # Still too large — trim duration proportionally
            last_compressed = compressed          # smallest quality attempt
            last_b64_kb = len(base64.b64encode(last_compressed)) / 1024
            trim_ratio = target_base64_kb / last_b64_kb
            trim_ms = int(len(audio) * min(trim_ratio, 1.0))
            trimmed = audio.set_frame_rate(8000)[:trim_ms]

            buf = io.BytesIO()
            trimmed.export(buf, format='mp3', bitrate='16k')
            compressed = buf.getvalue()
            logger.info(
                f"Trimmed to {trim_ms} ms and compressed to "
                f"{len(base64.b64encode(compressed)) / 1024:.1f} KB base64"
            )
            return compressed, 'mp3'

        except Exception as e:
            logger.warning(f"Compression failed ({e}), proceeding with original audio")
            return audio_bytes, audio_format
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

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
# VOICE DETECTOR  (with HuggingFace Inference API + retry / exponential back-off)
# ---------------------------------------------------------------------------
class VoiceDetector:
    def __init__(self):
        self.client = InferenceClient(
            token=Config.HF_API_TOKEN or None,
        )

    def analyze_voice(self, audio_bytes, audio_format, language):
        """Analyse voice with retries on rate-limit / transient errors."""
        last_error = None

        for attempt in range(1, Config.HF_MAX_RETRIES + 1):
            try:
                return self._call_hf_api(audio_bytes, language)
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                is_retryable = any(
                    kw in error_msg
                    for kw in ['429', 'rate', 'quota', 'loading', '503', 'timeout', 'connection', 'resolve']
                )
                if is_retryable and attempt < Config.HF_MAX_RETRIES:
                    wait = Config.HF_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"HuggingFace API issue (attempt {attempt}/{Config.HF_MAX_RETRIES}). "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                elif not is_retryable:
                    break

        logger.error(f"All HuggingFace API attempts failed: {type(last_error).__name__}: {last_error!r}")
        return self._fallback_analysis(audio_bytes, audio_format, language)

    def _call_hf_api(self, audio_bytes, language):
        """Call HuggingFace Inference API for audio classification."""
        if not Config.HF_API_TOKEN:
            raise RuntimeError("HuggingFace API token not configured")

        results = self.client.audio_classification(
            audio=audio_bytes,
            model=Config.HF_MODEL_ID,
            provider="hf-inference",
        )

        if results and len(results) > 0:
            top = max(results, key=lambda x: x.score)
            label = top.label.lower()
            score = float(top.score)

            if label == 'fake':
                classification = 'AI_GENERATED'
            elif label == 'real':
                classification = 'HUMAN'
            else:
                # Unexpected label — log and default to HUMAN
                logger.warning(f"Unexpected model label: '{top.label}'")
                classification = 'HUMAN'

            return {
                "classification": classification,
                "confidence_score": round(score, 2),
                "explanation": (
                    f"HuggingFace model classified as '{top.label}' "
                    f"with {score:.0%} confidence"
                ),
                "analysis_method": "huggingface_model",
            }

        raise ValueError("Unexpected response format from HuggingFace API")

    def _fallback_analysis(self, audio_bytes, audio_format, language):
        """Heuristic fallback when HuggingFace API is unavailable."""
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

        # --- Compress audio if base64 > 10 KB ---
        try:
            logger.info("STEP 4.5: Checking if audio needs compression...")
            audio_bytes, audio_format = AudioProcessor.compress_audio_if_needed(
                audio_bytes, audio_format, target_base64_kb=10
            )
        except ValueError as e:
            logger.error(f"STEP 4.5 FAILED: Compression error: {e}")
            return jsonify({
                "status": "error",
                "error_type": "processing_error",
                "message": str(e),
            }), 422

        # --- Voice analysis via HuggingFace ---
        logger.info("STEP 5: Sending audio to HuggingFace model for analysis...")
        analysis_result = voice_detector.analyze_voice(audio_bytes, audio_format, language)
        logger.info(f"STEP 5: Analysis complete - method={analysis_result.get('analysis_method')}, "
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
        "huggingface_configured": Config.HF_API_TOKEN is not None,
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
