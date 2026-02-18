# preprocessing.py
import re

class TextPreprocessor:
    def normalize(self, text):
        if not isinstance(text, str):
            return ""
        text = text.lower()
        text = re.sub(r"[^\w\s.,!?]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
