# backend/voice/models.py
import numpy as np
import librosa
from scipy.spatial.distance import cosine
import random
from dataclasses import dataclass
from typing import Optional, Tuple, List
import json
import tempfile
import os
from difflib import SequenceMatcher
from pydub import AudioSegment

@dataclass
class VoiceSample:
    """Container for voice sample data"""
    audio_data: np.ndarray
    sample_rate: int
    duration: float
    spoken_text: str = ""

class VoiceEmbeddingModel:
    """Speaker verification using MFCC features"""
    
    def __init__(self):
        self.threshold = 0.8  # Set threshold to 0.8 as requested
    
    def extract_features(self, audio_path: str):
        """Extract MFCC features from audio"""
        try:
            audio, sr = librosa.load(audio_path, sr=16000)
            mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
            mfcc_mean = np.mean(mfccs, axis=1)
            mfcc_std = np.std(mfccs, axis=1)
            features = np.concatenate([mfcc_mean, mfcc_std])
            features = (features - np.mean(features)) / (np.std(features) + 1e-10)
            return features
        except Exception as e:
            print(f"Error extracting features: {e}")
            return np.random.randn(26)  # Fallback
    
    def create_embedding(self, audio_path: str) -> List[float]:
        """Create voice embedding"""
        features = self.extract_features(audio_path)
        return features.tolist()
    
    def verify_speaker(self, stored_embedding: List[float], 
                      new_embedding: List[float], 
                      threshold: float = None) -> Tuple[bool, float]:
        """Verify if embeddings match using cosine similarity"""
        if threshold is None:
            threshold = self.threshold  # Use default threshold of 0.8
            
        if not stored_embedding or not new_embedding:
            return False, 0.0
            
        try:
            # Convert to numpy arrays
            stored_arr = np.array(stored_embedding)
            new_arr = np.array(new_embedding)
            
            # Handle different lengths
            if len(stored_arr) != len(new_arr):
                min_len = min(len(stored_arr), len(new_arr))
                stored_arr = stored_arr[:min_len]
                new_arr = new_arr[:min_len]
            
            # Calculate cosine similarity
            similarity = 1 - cosine(stored_arr, new_arr)
            
            return similarity >= threshold, float(similarity)
        except Exception as e:
            print(f"Error verifying speaker: {e}")
            return False, 0.0

class AudioQualityValidator:
    """Validate audio quality before processing"""
    
    def __init__(self):
        self.min_duration = 1.0  # seconds
        self.max_duration = 10.0  # seconds
        self.min_rms = 0.01  # minimum volume
        
    def validate(self, audio_path: str) -> Tuple[bool, str]:
        """Validate audio file quality"""
        try:
            audio, sr = librosa.load(audio_path, sr=16000, mono=True)
            duration = len(audio) / sr
            
            # Check duration
            if duration < self.min_duration:
                return False, f"Audio too short (min {self.min_duration}s)"
            if duration > self.max_duration:
                return False, f"Audio too long (max {self.max_duration}s)"
            
            # Check volume (RMS)
            rms = np.sqrt(np.mean(audio**2))
            if rms < self.min_rms:
                return False, "Audio too quiet"
            
            return True, "Audio quality OK"
        except Exception as e:
            return False, f"Error processing audio: {str(e)}"

class VoiceSecurityManager:
    """Generate numeric challenge texts"""
    
    def __init__(self):
        pass
    
    def generate_challenge(self) -> str:
        """Generate 6-digit numeric challenge"""
        return str(random.randint(100000, 999999))