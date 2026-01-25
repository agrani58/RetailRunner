# backend/voice/speech_verifier.py
import whisper
import tempfile
import os
import re
from typing import Tuple
import librosa
import soundfile as sf

class SpeechVerifier:
    def __init__(self):
        # Load Whisper model once at startup
        print("Loading Whisper model...")
        self.model = whisper.load_model("base")
        print("Whisper model loaded successfully")
        
        # Number word to digit mapping
        self.number_map = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
            'ten': '10'
        }
    
    def extract_digits_from_text(self, text: str) -> str:
        """Extract digits from text, handling both numeric and word forms"""
        # First, extract any actual digits
        digits = re.findall(r'\d+', text)
        result = ''.join(digits)
        
        # If we don't have enough digits, try to extract from words
        if len(result) < 6:
            text_lower = text.lower()
            
            # Try to find number words
            for word, digit in self.number_map.items():
                if word in text_lower:
                    # Count occurrences
                    count = text_lower.count(word)
                    result += digit * count
            
            # Also handle common spoken number patterns
            patterns = {
                'double': lambda t: t.replace('double', ''),
                'triple': lambda t: t.replace('triple', '')
            }
            
            # Handle "and" as separator
            text_clean = text_lower.replace(' and ', ' ')
            text_clean = text_clean.replace(',', ' ')
            
            # Split and look for individual number words
            words = text_clean.split()
            for word in words:
                if word in self.number_map:
                    result += self.number_map[word]
        
        return result
    
    def verify_challenge_speech(self, audio_path: str, expected_text: str) -> Tuple[bool, str, str]:
        """
        Verify that the audio contains the expected challenge text.
        Returns: (is_correct, spoken_text, message)
        """
        try:
            # Transcribe audio using Whisper
            result = self.model.transcribe(audio_path, language="en", fp16=False)
            spoken_text = result["text"].strip()
            
            # Extract expected digits
            expected_digits = ''.join(filter(str.isdigit, expected_text))
            
            # Extract spoken digits
            spoken_digits = self.extract_digits_from_text(spoken_text)
            
            print(f"SPEECH VERIFIER DEBUG: Expected digits: {expected_digits}")
            print(f"SPEECH VERIFIER DEBUG: Spoken text: '{spoken_text}'")
            print(f"SPEECH VERIFIER DEBUG: Spoken digits extracted: '{spoken_digits}'")
            
            # Check if we have enough digits
            if not spoken_digits:
                return False, spoken_text, "No numbers detected in your speech"
            
            # Check if spoken digits start with expected digits (allow for extra words)
            # We'll take the first 6 digits of what was spoken
            if len(spoken_digits) >= len(expected_digits):
                spoken_first_digits = spoken_digits[:len(expected_digits)]
                if spoken_first_digits == expected_digits:
                    return True, spoken_text, "Speech matches challenge text"
                else:
                    return False, spoken_text, f"Spoken numbers '{spoken_first_digits}' do not match expected '{expected_digits}'"
            else:
                # Try to see if expected digits contain spoken digits (partial match)
                if expected_digits.startswith(spoken_digits):
                    return False, spoken_text, f"Spoken only {len(spoken_digits)} numbers, expected {len(expected_digits)}"
                else:
                    return False, spoken_text, f"Spoken numbers '{spoken_digits}' do not match expected '{expected_digits}'"
                
        except Exception as e:
            print(f"Speech verification error: {e}")
            return False, "", f"Speech verification failed: {str(e)}"

# Create a global instance
speech_verifier = SpeechVerifier()