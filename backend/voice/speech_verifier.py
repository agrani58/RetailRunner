import whisper
import tempfile
import os
import re
from typing import Tuple, List
import numpy as np
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("speech_verifier")

class SpeechVerifier:
    def __init__(self):
        # Load Whisper model once at startup
        logger.info("Loading Whisper model...")
        try:
            self.model = whisper.load_model("base")
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
        
        # Single-digit number word to digit mapping
        self.number_map = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
        }
    
    def normalize_transcription(self, text: str) -> str:
        """Normalize transcription text"""
        return text.lower().strip()
    
    def extract_digits_from_text(self, text: str) -> str:
        """Extract digits from text - STRICT VERSION"""
        result = []
        text_lower = text.lower()
        
        # Clean text - remove punctuation except spaces
        text_clean = re.sub(r'[^\w\s]', '', text_lower)
        
        # Split into words
        words = text_clean.split()
        
        # Pattern to match individual digits (1-9)
        digit_pattern = re.compile(r'^[1-9]$')
        
        for word in words:
            # Check if word is a single digit
            if digit_pattern.match(word):
                result.append(word)
            # Check if word is a number word (0-9)
            elif word in self.number_map:
                result.append(self.number_map[word])
            # Check if word contains multiple digits (like "123")
            elif re.search(r'\d+', word):
                # Extract all digits from the word
                digits_in_word = re.findall(r'\d', word)
                result.extend(digits_in_word)
        
        # Filter only digits 0-9
        filtered_result = [d for d in result if d.isdigit() and len(d) == 1]
        
        return ''.join(filtered_result)
    
    def verify_challenge_speech(self, audio_path: str, expected_text: str) -> Tuple[bool, str, str]:
        """
        STRICT verification that the audio contains the expected challenge text EXACTLY.
        Returns: (is_correct, spoken_text, message)
        """
        try:
            logger.info(f"Starting speech verification for challenge: {expected_text}")
            
            # Transcribe audio using Whisper
            logger.info(f"Transcribing audio: {audio_path}")
            result = self.model.transcribe(audio_path, language="en", fp16=False, temperature=0.0)
            raw_spoken_text = result["text"].strip()
            
            # Normalize the transcription
            spoken_text = self.normalize_transcription(raw_spoken_text)
            
            # Extract digits from spoken text
            spoken_digits = self.extract_digits_from_text(spoken_text)
            
            logger.info(f"Verification - Expected: '{expected_text}', Spoken digits: '{spoken_digits}'")
            logger.info(f"Full transcription: '{raw_spoken_text}' -> '{spoken_text}'")
            
            # Extract expected digits (remove any non-digit characters)
            expected_digits = ''.join(filter(str.isdigit, expected_text))
            
            # STRICT EXACT MATCH VERIFICATION
            if not spoken_digits:
                return False, spoken_text, "No numbers detected in your speech. Please speak each digit clearly."
            
            # Must be EXACTLY the same digits in the same order
            if spoken_digits == expected_digits:
                logger.info(f"Speech verification PASSED for challenge: {expected_digits}")
                return True, spoken_text, "Speech matches challenge text"
            else:
                # Generic error message
                return False, spoken_text, "Does not match challenge strings"
                
        except Exception as e:
            logger.error(f"Speech verification error: {e}")
            import traceback
            traceback.print_exc()
            return False, "", f"Speech verification failed: {str(e)}"
    
    def check_audio_quality(self, audio_path: str) -> Tuple[bool, str]:
        """Check basic audio quality"""
        try:
            import librosa
            import soundfile as sf
            
            # Get audio duration and sample rate
            info = sf.info(audio_path)
            duration = info.duration
            
            if duration < 1.0:
                return False, "Audio too short (minimum 1 second)"
            if duration > 10.0:
                return False, "Audio too long (maximum 10 seconds)"
            
            # Load and check volume
            audio, sr = librosa.load(audio_path, sr=16000, mono=True)
            rms = np.sqrt(np.mean(audio**2))
            
            if rms < 0.01:
                return False, "Audio too quiet. Please speak louder."
            
            return True, "Audio quality OK"
        except Exception as e:
            return False, f"Audio quality check failed: {str(e)}"

# Create a global instance
speech_verifier = SpeechVerifier()