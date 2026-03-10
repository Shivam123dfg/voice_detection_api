"""
Generate a synthetic speech-like MP3 test file and call the deployed API.
No internet needed for audio generation — uses numpy + pydub locally.
"""
import numpy as np
import base64
import json
import sys
import os

def generate_test_audio(output_path="test_audio.mp3", duration_sec=3):
    """Generate a speech-like synthetic MP3 test file."""
    import subprocess
    import wave
    import struct

    # Point pydub to the bundled ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]
        # Also tell pydub directly
        from pydub import AudioSegment
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffprobe = ffmpeg_path
    except ImportError:
        from pydub import AudioSegment

    sample_rate = 22050
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)

    f0 = 150
    signal = np.zeros_like(t)

    for harmonic in range(1, 6):
        freq = f0 * harmonic
        vibrato = 5 * np.sin(2 * np.pi * 5 * t)
        amplitude = 1.0 / harmonic
        signal += amplitude * np.sin(2 * np.pi * (freq + vibrato) * t)

    envelope = np.ones_like(t)
    words = int(duration_sec * 2)
    for i in range(words):
        pause_start = int((i + 0.8) / words * len(t))
        pause_end = int((i + 1.0) / words * len(t))
        if pause_end <= len(t):
            envelope[pause_start:pause_end] *= 0.1

    signal *= envelope
    signal = signal / np.max(np.abs(signal)) * 0.8
    samples = (signal * 32767).astype(np.int16)

    audio = AudioSegment(
        samples.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1,
    )
    audio.export(output_path, format="mp3")

    file_size = os.path.getsize(output_path)
    print(f"Generated: {output_path} ({file_size} bytes, {duration_sec}s)")
    return output_path


def encode_and_test(mp3_path, language="English"):
    """Base64 encode an MP3 file and call the deployed API."""
    print(f"\nEncoding: {mp3_path}")
    with open(mp3_path, "rb") as f:
        audio_bytes = f.read()
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    print(f"Base64 length: {len(audio_b64)} chars ({len(audio_bytes)} bytes raw)")

    payload = {
        "language": language,
        "audioFormat": "mp3",
        "audioBase64": audio_b64,
    }

    # Save payload to file (for curl)
    payload_path = "test_payload_live.json"
    with open(payload_path, "w") as f:
        json.dump(payload, f)
    print(f"Payload saved to: {payload_path}")

    # Try calling API directly with requests (if available and network allows)
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass

    try:
        import requests
        print("\nCalling API...")
        url = os.environ.get("API_URL", "https://api-voice-detection-10h6.onrender.com/api/voice-detection")
        api_key = os.environ.get("API_SECRET_KEY", "sk_test_voice_detection_2024")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        print(f"Status: {resp.status_code}")
        print(f"Response:\n{json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"\nCouldn't call API directly ({e}).")
        print(f"Run this curl command instead:\n")
        api_key = os.environ.get("API_SECRET_KEY", "your_api_secret_key")
        api_url = os.environ.get("API_URL", "https://your-app.onrender.com/api/voice-detection")
        print(f'curl.exe -X POST "{api_url}" '
              f'-H "Content-Type: application/json" '
              f'-H "x-api-key: {api_key}" '
              f'-d @{payload_path}')


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Use provided MP3 file
        mp3_file = sys.argv[1]
        lang = sys.argv[2] if len(sys.argv) > 2 else "English"
    else:
        # Generate synthetic audio
        print("No MP3 file provided — generating synthetic test audio...\n")
        mp3_file = generate_test_audio()
        lang = "English"

    encode_and_test(mp3_file, lang)
