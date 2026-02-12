import os
import spacy
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class MLNERModel:
    def __init__(self, model_path: str):
        """Load spaCy NER model from the given path."""
        model_path = os.path.abspath(model_path)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"❌ spaCy model not found: {model_path}")

        logger.info(f"🔹 Loading spaCy NER model from: {model_path}")
        try:
            self.nlp = spacy.load(model_path)
            logger.info(f"✅ spaCy model loaded: {self.nlp.lang}, pipes: {self.nlp.pipe_names}")
        except Exception:
            logger.warning("⚠️ Could not load full model, falling back to blank 'en'")
            self.nlp = spacy.blank("en")

    def extract(self, text: str) -> Dict[str, Any]:
        """Extract product entities – now also extracts bigram product terms."""
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            return {"products": []}

        doc = self.nlp(text)
        products = []

        # 1️⃣ Try trained NER first
        if "ner" in self.nlp.pipe_names:
            for ent in doc.ents:
                if ent.label_ in ("PRODUCT", "PRODUCT_TYPE", "PRODUCT_NAME"):
                    products.append({
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "confidence": 0.95
                    })

        # 2️⃣ Fallback: extract NOUN + NOUN bigrams (e.g. "lip balm", "face wash")
        if not products:
            # Collect noun chunks (more accurate than simple bigrams)
            for chunk in doc.noun_chunks:
                text = chunk.text.lower().strip()
                # Keep only if it looks like a product term (2-3 words)
                if 2 <= len(text.split()) <= 3 and not any(w in self.nlp.Defaults.stop_words for w in text.split()[:2]):
                    products.append({
                        "text": chunk.text,
                        "label": "PRODUCT_TYPE",
                        "start": chunk.start_char,
                        "end": chunk.end_char,
                        "confidence": 0.7
                    })

            # 3️⃣ Still nothing? Simple bigram scan
            if not products:
                tokens = [t for t in doc if not t.is_punct and not t.is_space]
                for i in range(len(tokens) - 1):
                    if tokens[i].pos_ == "NOUN" and tokens[i+1].pos_ == "NOUN":
                        bigram = f"{tokens[i]} {tokens[i+1]}"
                        products.append({
                            "text": bigram,
                            "label": "PRODUCT_TYPE",
                            "start": tokens[i].idx,
                            "end": tokens[i+1].idx + len(tokens[i+1].text),
                            "confidence": 0.6
                        })
                        break  # take first bigram only

        # 4️⃣ Clean entities (remove trailing punctuation, lowercase)
        cleaned = []
        seen = set()
        for ent in products:
            clean = ent["text"].strip().rstrip("?!,.;:").lower()
            if clean and clean not in seen:
                seen.add(clean)
                ent["text"] = clean
                cleaned.append(ent)

        logger.info(f"🧠 NER extracted {len(cleaned)} product entities: {[e['text'] for e in cleaned]}")
        return {"products": cleaned}