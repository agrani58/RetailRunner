import re
import logging
from typing import Set

import spacy
from spacy.lang.en.stop_words import STOP_WORDS

logger = logging.getLogger(__name__)

# Global spaCy model – disable parser/ner for speed
try:
    nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    logger.info("✅ spaCy loaded for lemmatisation + stopwords")
except OSError:
    logger.error("❌ spaCy model 'en_core_web_sm' not found. Run: python -m spacy download en_core_web_sm")
    raise


class TextNormalizer:
    """
    Minimal, fast normaliser using spaCy.
    - Lowercasing
    - Lemmatisation (nouns, verbs, adjectives)
    - Stopword removal
    No manual phrase corrections – we rely on fuzzy fallback.
    """

    def __init__(self):
        self.stopwords = STOP_WORDS

    def normalize(self, text: str) -> str:
        """Lemmatize, lowercase, remove stopwords and short tokens."""
        if not text:
            return ""
        doc = nlp(text.lower())
        tokens = [
            token.lemma_
            for token in doc
            if token.text not in self.stopwords
            and token.pos_ in ("NOUN", "VERB", "ADJ", "PROPN")
            and len(token.text) > 2
        ]
        return " ".join(tokens)

    def lemmatize(self, text: str) -> str:
        """Lemmatize without removing stopwords (used for product fields)."""
        if not text:
            return ""
        doc = nlp(text.lower())
        return " ".join([token.lemma_ for token in doc])

    def remove_stopwords(self, text: str) -> str:
        doc = nlp(text.lower())
        return " ".join([token.text for token in doc if token.text not in self.stopwords])

nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])