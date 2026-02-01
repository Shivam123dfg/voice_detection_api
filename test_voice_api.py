import requests
import base64
import json
import os

class VoiceDetectionClient:
    def __init__(self, base_url="http://localhost:5000", api_key="sk_test_voice_detection_2024"):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key
        }
    
    def encode_audio_file(self, file_path):
        """Convert audio file to base64"""
        try:
            with open(file_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
                base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
                return base64_audio
        except FileNotFoundError:
            print(f"Error: File {file_path} not found")
            return None
        except Exception as e:
            print(f"Error encoding file: {e}")
            return None
    
    def detect_voice(self, audio_file_path, language="English"):
        """Send audio file for voice detection"""
        # Encode audio file
        base64_audio = self.encode_audio_file(audio_file_path)
        if not base64_audio:
            return None
        
        # Prepare request data
        request_data = {
            "language": language,
            "audioFormat": "mp3",
            "audioBase64": base64_audio
        }
        
        try:
            # Make API request
            response = requests.post(
                f"{self.base_url}/api/voice-detection",
                headers=self.headers,
                json=request_data,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API Error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None
    
    def health_check(self):
        """Check API health"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Health check failed: {e}")
            return None

def main():
    # Initialize client
    # For local testing
    client = VoiceDetectionClient("http://localhost:5000")
    
    # For deployed API (replace with your actual URL)
    # client = VoiceDetectionClient("https://your-domain.com")
    
    print("Voice Detection API Test Client")
    print("=" * 40)
    
    # Health check
    print("1. Checking API health...")
    health = client.health_check()
    if health:
        print(f"API Status: {health}")
    else:
        print("❌ API is not responding!")
        return
    
    print("\n2. Testing voice detection...")
    
    # Test with sample audio file (you need to provide this)
    audio_file = "sample_audio.mp3"  # Replace with your test audio file
    
    if not os.path.exists(audio_file):
        print(f"❌ Test audio file '{audio_file}' not found!")
        print("\nTo test the API:")
        print("1. Place an MP3 audio file in the same directory")
        print("2. Update the 'audio_file' variable with the filename")
        return
    
    # Test different languages
    test_languages = ["English", "Tamil", "Hindi", "Malayalam", "Telugu"]
    
    for language in test_languages:
        print(f"\nTesting with language: {language}")
        result = client.detect_voice(audio_file, language)
        
        if result:
            print("✅ Detection Result:")
            print(f"   Status: {result.get('status')}")
            print(f"   Language: {result.get('language')}")
            print(f"   Classification: {result.get('classification')}")
            print(f"   Confidence: {result.get('confidenceScore')}")
            print(f"   Explanation: {result.get('explanation')}")
        else:
            print(f"❌ Failed to detect voice for {language}")
        
        print("-" * 40)

def test_with_custom_audio():
    """Test with custom audio file"""
    client = VoiceDetectionClient()
    
    print("Custom Audio Test")
    print("=" * 20)
    
    audio_file = input("Enter path to MP3 file: ").strip()
    language = input("Enter language (Tamil/English/Hindi/Malayalam/Telugu): ").strip()
    
    if language not in ["Tamil", "English", "Hindi", "Malayalam", "Telugu"]:
        print("Invalid language. Using English as default.")
        language = "English"
    
    result = client.detect_voice(audio_file, language)
    
    if result:
        print("\n✅ Detection Result:")
        print(json.dumps(result, indent=2))
    else:
        print("❌ Detection failed!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "custom":
        test_with_custom_audio()
    else:
        main()

# Example cURL command for testing:
"""
curl -X POST http://localhost:5000/api/voice-detection \
-H "Content-Type: application/json" \
-H "x-api-key: sk_test_voice_detection_2024" \
-d '{
    "language": "English",
    "audioFormat": "mp3",
    "audioBase64": "BASE64_ENCODED_AUDIO_DATA_HERE"
}'
"""