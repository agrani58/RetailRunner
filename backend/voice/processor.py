# backend/voice/processor.py
import tempfile
import os
import librosa
import soundfile as sf
import numpy as np

class AudioProcessor:
    def __init__(self, target_sr=16000):
        self.target_sr = target_sr
    
    def reduce_noise(self, audio, sr):
        """Simple noise reduction using spectral subtraction"""
        # Compute STFT
        stft = librosa.stft(audio, n_fft=2048, hop_length=512)
        magnitude = np.abs(stft)
        
        # Estimate noise from first 0.5 seconds
        noise_frames = magnitude[:, :int(0.5 * sr / 512)]
        noise_mean = np.mean(noise_frames, axis=1, keepdims=True)
        
        # Apply spectral subtraction
        magnitude_clean = np.maximum(magnitude - 2 * noise_mean, 0)
        
        # Reconstruct audio
        stft_clean = magnitude_clean * np.exp(1j * np.angle(stft))
        audio_clean = librosa.istft(stft_clean, hop_length=512)
        
        return audio_clean
    
    def process_audio(self, audio_bytes: bytes):
        """Process audio bytes"""
        # Create temp file with .wav extension for librosa
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_bytes)
            path = f.name
        
        try:
            # Load audio
            audio, sr = librosa.load(path, sr=self.target_sr, mono=True)
            
            # Apply noise reduction if audio is long enough
            if len(audio) > sr * 0.5:  # At least 0.5 seconds
                audio = self.reduce_noise(audio, sr)
            
            # Normalize
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))
            
            # Save processed audio
            sf.write(path, audio, sr)
            return path, len(audio) / sr
        except Exception as e:
            print(f"Error processing audio: {e}")
            # Return original path and estimated duration
            return path, len(audio_bytes) / (2 * self.target_sr)
    
    def cleanup(self, path: str):
        """Remove temp file"""
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Error cleaning up file {path}: {e}")
    
    def validate_recording(self, audio_bytes: bytes):
        """Validate audio recording - returns (is_valid, message, path)"""
        if len(audio_bytes) == 0:
            return False, "No audio data", None
        
        try:
            # Create temp file for validation
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
                f.write(audio_bytes)
                temp_path = f.name
            
            # Convert to WAV for processing if needed
            if temp_path.endswith('.webm') or temp_path.endswith('.mp3'):
                try:
                    # Try to load with librosa (it can handle various formats)
                    audio, sr = librosa.load(temp_path, sr=self.target_sr, mono=True)
                    wav_path = tempfile.mktemp(suffix='.wav')
                    sf.write(wav_path, audio, sr)
                    
                    # Clean up original temp file
                    os.remove(temp_path)
                    temp_path = wav_path
                except Exception as e:
                    print(f"Error converting audio: {e}")
                    # If conversion fails, use original
                    pass
            
            # Load and validate
            audio, sr = librosa.load(temp_path, sr=self.target_sr, mono=True)
            duration = len(audio) / sr
            
            if duration < 1.0:
                self.cleanup(temp_path)
                return False, "Too short (minimum 1 second)", None
            
            if duration > 10.0:
                self.cleanup(temp_path)
                return False, "Too long (maximum 10 seconds)", None
            
            # Check volume (RMS)
            rms = np.sqrt(np.mean(audio**2))
            if rms < 0.01:
                self.cleanup(temp_path)
                return False, "Too quiet", None
            
            return True, "Valid", temp_path
            
        except Exception as e:
            print(f"Error validating recording: {e}")
            return False, f"Validation error: {str(e)}", None