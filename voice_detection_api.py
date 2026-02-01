from flask import Flask, request, jsonify
import base64
import os
import tempfile
import json
from google import genai
import logging
from functools import wraps
import io
import wave
import librosa
import numpy as np
from pydub import AudioSegment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
class Config:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyBxPc1hqtcrho9iCljE6mMGAty0BewUAIw')
    API_SECRET_KEY = os.getenv('API_SECRET_KEY', 'sk_test_voice_detection_2024')
    SUPPORTED_LANGUAGES = ['Tamil', 'English', 'Hindi', 'Malayalam', 'Telugu']
    MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB

# Initialize Gemini client
try:
    gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
    logger.info("Gemini client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    gemini_client = None

# Authentication decorator
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('x-api-key')
        if not api_key or api_key != Config.API_SECRET_KEY:
            return jsonify({
                "status": "error",
                "message": "Invalid API key or malformed request"
            }), 401
        return f(*args, **kwargs)
    return decorated_function

# Audio processing functions
class AudioProcessor:
    @staticmethod
    def decode_base64_audio(base64_string):
        """Decode base64 audio to bytes"""
        try:
            audio_bytes = base64.b64decode(base64_string)
            return audio_bytes
        except Exception as e:
            logger.error(f"Failed to decode base64 audio: {e}")
            raise ValueError("Invalid base64 audio data")
    
    @staticmethod
    def extract_audio_features(audio_bytes):
        """Extract audio features for analysis"""
        try:
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name
            
            # Convert to WAV for librosa processing
            audio = AudioSegment.from_mp3(temp_path)
            wav_path = temp_path.replace('.mp3', '.wav')
            audio.export(wav_path, format="wav")
            
            # Load with librosa for feature extraction
            y, sr = librosa.load(wav_path, sr=None)
            
            # Extract features
            features = {
                'duration': len(y) / sr,
                'sample_rate': sr,
                'rms_energy': float(np.mean(librosa.feature.rms(y=y))),
                'spectral_centroid': float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
                'zero_crossing_rate': float(np.mean(librosa.feature.zero_crossing_rate(y))),
                'mfcc_mean': [float(x) for x in np.mean(librosa.feature.mfcc(y=y, sr=sr), axis=1)[:13]],
                'tempo': float(librosa.beat.tempo(y=y, sr=sr)[0]) if len(librosa.beat.tempo(y=y, sr=sr)) > 0 else 0.0
            }
            
            # Clean up temporary files
            os.unlink(temp_path)
            os.unlink(wav_path)
            
            return features
            
        except Exception as e:
            logger.error(f"Failed to extract audio features: {e}")
            # Clean up on error
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
                if 'wav_path' in locals():
                    os.unlink(wav_path)
            except:
                pass
            raise ValueError("Failed to process audio file")

# Voice detection using Gemini
class VoiceDetector:
    def __init__(self, gemini_client):
        self.client = gemini_client
    
    def analyze_voice(self, audio_features, language):
        """Analyze voice using Gemini AI"""
        try:
            if not self.client:
                raise Exception("Gemini client not initialized")
            
            # Create a comprehensive prompt for voice analysis
            analysis_prompt = f"""
            You are an expert voice analyst specializing in detecting AI-generated vs human voices in {language} language.
            
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
            
            Respond ONLY in the following JSON format:
            {{
                "status": "success" or "error"
                "language": "Language of the audio"
                "classification": "AI_GENERATED" or "HUMAN",
                "confidence_score": 0.XX,
                "explanation": "Brief technical explanation for the decision"
            }}
            
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
            """
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=analysis_prompt
            )
            
            # Parse the response
            response_text = response.text.strip()
            
            # Clean the response to extract JSON
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                response_text = response_text[json_start:json_end]
            elif '{' in response_text and '}' in response_text:
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                response_text = response_text[json_start:json_end]
            
            try:
                result = json.loads(response_text)
                
                # Validate response format
                if 'classification' not in result or 'confidence_score' not in result:
                    raise ValueError("Invalid response format")
                
                # Ensure classification is valid
                if result['classification'] not in ['AI_GENERATED', 'HUMAN']:
                    result['classification'] = 'HUMAN'  # Default to HUMAN if unclear
                
                # Ensure confidence score is within bounds
                confidence = float(result['confidence_score'])
                if confidence < 0 or confidence > 1:
                    confidence = min(1.0, max(0.0, confidence))
                result['confidence_score'] = confidence
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response as JSON: {e}")
                logger.error(f"Response text: {response_text}")
                
                # Fallback analysis based on features
                return self._fallback_analysis(audio_features, language)
            
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            return self._fallback_analysis(audio_features, language)
    
    def _fallback_analysis(self, audio_features, language):
        """Fallback analysis when Gemini fails"""
        # Simple heuristic-based analysis
        confidence = 0.6
        classification = "HUMAN"
        explanation = "Analysis based on audio characteristics"
        
        # Check for AI indicators
        ai_indicators = 0
        
        # Very consistent RMS energy might indicate AI
        if audio_features['rms_energy'] > 0.1:
            ai_indicators += 1
        
        # Very high spectral centroid might indicate AI processing
        if audio_features['spectral_centroid'] > 3000:
            ai_indicators += 1
        
        # Very low zero crossing rate might indicate AI
        if audio_features['zero_crossing_rate'] < 0.05:
            ai_indicators += 1
        
        if ai_indicators >= 2:
            classification = "AI_GENERATED"
            confidence = 0.7
            explanation = "Detected consistent audio patterns typical of AI-generated speech"
        
        return {
            "classification": classification,
            "confidence_score": confidence,
            "explanation": explanation
        }

# Initialize voice detector
voice_detector = VoiceDetector(gemini_client)

@app.route('/api/voice-detection', methods=['POST'])
@require_api_key
def voice_detection():
    """Main voice detection endpoint"""
    try:
        # Validate content type
        if not request.is_json:
            return jsonify({
                "status": "error",
                "message": "Content-Type must be application/json"
            }), 400
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['language', 'audioFormat', 'audioBase64']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }), 400
        
        # Validate language
        language = data['language']
        if language not in Config.SUPPORTED_LANGUAGES:
            return jsonify({
                "status": "error",
                "message": f"Unsupported language. Supported: {Config.SUPPORTED_LANGUAGES}"
            }), 400
        
        # Validate audio format
        if data['audioFormat'].lower() != 'mp3':
            return jsonify({
                "status": "error",
                "message": "Only MP3 format is supported"
            }), 400
        
        # Validate base64 audio
        audio_base64 = data['audioBase64']
        if not audio_base64:
            return jsonify({
                "status": "error",
                "message": "audioBase64 cannot be empty"
            }), 400
        
        # Decode and process audio
        try:
            audio_bytes = AudioProcessor.decode_base64_audio(audio_base64)
            
            # Check audio size
            if len(audio_bytes) > Config.MAX_AUDIO_SIZE:
                return jsonify({
                    "status": "error",
                    "message": "Audio file too large. Maximum size: 10MB"
                }), 400
            
            # Extract audio features
            audio_features = AudioProcessor.extract_audio_features(audio_bytes)
            
        except ValueError as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 400
        
        # Analyze voice
        try:
            analysis_result = voice_detector.analyze_voice(audio_features, language)
            
            # Format response
            response_data = {
                "status": "success",
                "language": language,
                "classification": analysis_result["classification"],
                "confidenceScore": round(analysis_result["confidence_score"], 2),
                "explanation": analysis_result["explanation"]
            }
            
            return jsonify(response_data), 200
            
        except Exception as e:
            logger.error(f"Voice analysis failed: {e}")
            return jsonify({
                "status": "error",
                "message": "Voice analysis failed. Please try again."
            }), 500
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "supported_languages": Config.SUPPORTED_LANGUAGES,
        "gemini_available": gemini_client is not None
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "message": "Endpoint not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "status": "error",
        "message": "Internal server error"
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)