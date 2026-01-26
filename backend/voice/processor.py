# \backend\voice\processor.py
import tempfile
import os
import librosa
import soundfile as sf
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger("audio_processor")

class AudioProcessor:
    def __init__(self, target_sr=16000):
        self.target_sr = target_sr
    
    def reduce_noise(self, audio, sr):
        """Simple noise reduction using spectral subtraction"""
        try:
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
        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return audio
    
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
                audio = audio / np.max(np.abs(audio)) * 0.9  # Leave some headroom
            
            # Save processed audio
            sf.write(path, audio, sr)
            return path, len(audio) / sr
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            # Return original path and estimated duration
            return path, len(audio_bytes) / (2 * self.target_sr)
    
    def check_speech_clarity(self, audio_path: str) -> Tuple[bool, str]:
        """Check if audio contains clear speech"""
        try:
            audio, sr = librosa.load(audio_path, sr=self.target_sr, mono=True)
            
            # Calculate spectral centroid (indicator of speech quality)
            spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)
            centroid_mean = np.mean(spectral_centroid)
            
            # Calculate zero-crossing rate (speech vs noise)
            zcr = librosa.feature.zero_crossing_rate(audio)
            zcr_mean = np.mean(zcr)
            
            # Check for background noise
            energy = np.sum(audio**2) / len(audio)
            
            logger.info(f"Audio quality - Centroid: {centroid_mean:.1f}, ZCR: {zcr_mean:.3f}, Energy: {energy:.6f}")
            
            if centroid_mean < 500:  # Too low frequency (likely not speech)
                return False, "Audio doesn't sound like clear speech"
            if energy < 0.0001:  # Too quiet
                return False, "Audio is too quiet. Please speak louder."
            if zcr_mean < 0.01:  # Too few zero crossings (likely not speech)
                return False, "Audio quality too poor for speech recognition"
            
            # Check for silence
            rms = librosa.feature.rms(y=audio)
            if np.max(rms) < 0.01:
                return False, "Audio contains mostly silence"
            
            return True, "Speech clarity OK"
        except Exception as e:
            return False, f"Audio clarity check failed: {str(e)}"
    
    def cleanup(self, path: str):
        """Remove temp file"""
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"Error cleaning up file {path}: {e}")
    
    def validate_recording(self, audio_bytes: bytes) -> Tuple[bool, str, str]:
        """Validate audio recording - returns (is_valid, message, path)"""
        if len(audio_bytes) == 0:
            return False, "No audio data", None
        
        if len(audio_bytes) < 1000:  # Less than 1KB
            return False, "Audio file too small", None
        
        try:
            # Create temp file
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
                f.write(audio_bytes)
                temp_path = f.name
            
            # Convert to WAV if needed
            if not temp_path.endswith('.wav'):
                try:
                    audio, sr = librosa.load(temp_path, sr=self.target_sr, mono=True)
                    wav_path = tempfile.mktemp(suffix='.wav')
                    sf.write(wav_path, audio, sr)
                    
                    # Clean up original temp file
                    os.remove(temp_path)
                    temp_path = wav_path
                except Exception as e:
                    logger.warning(f"Error converting audio: {e}")
                    # If conversion fails, try to load anyway
                    pass
            
            # Load and validate
            audio, sr = librosa.load(temp_path, sr=self.target_sr, mono=True)
            duration = len(audio) / sr
            
            if duration < 1.5:
                self.cleanup(temp_path)
                return False, "Too short (minimum 1.5 seconds)", None
            
            if duration > 15.0:
                self.cleanup(temp_path)
                return False, "Too long (maximum 15 seconds)", None
            
            # Check volume (RMS)
            rms = np.sqrt(np.mean(audio**2))
            if rms < 0.005:
                self.cleanup(temp_path)
                return False, "Too quiet. Please speak louder and closer to the microphone.", None
            
            # Check speech clarity
            clarity_ok, clarity_msg = self.check_speech_clarity(temp_path)
            if not clarity_ok:
                self.cleanup(temp_path)
                return False, clarity_msg, None
            
            return True, "Valid", temp_path
            
        except Exception as e:
            logger.error(f"Error validating recording: {e}")
            return False, f"Validation error: {str(e)}", None