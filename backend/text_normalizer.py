import re
import inflect
import spacy
from spacy.lang.en.stop_words import STOP_WORDS

class TextNormalizer:
    """
    Normalizes text for search:
    - lowercases
    - removes punctuation
    - removes stopwords (optional, for semantic search)
    - lemmatizes using spaCy
    - converts plural to singular (extra safety)
    """
    def __init__(self):
        try:
            # Load small English model – disable parser/ner for speed
            self.nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        except OSError:
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
        self.inflect_engine = inflect.engine()

    def normalize(self, text: str, for_semantic: bool = True) -> str:
        """
        for_semantic=True: remove stopwords (for search queries)
        for_semantic=False: keep stopwords (for constraint extraction)
        """
        if not isinstance(text, str) or not text.strip():
            return ""
        doc = self.nlp(text.lower())
        tokens = []
        for token in doc:
            if token.is_punct or token.is_space:
                continue
            if for_semantic and token.is_stop:
                continue
            # Lemmatize (spaCy lemmatizer handles plural→singular well)
            lemma = token.lemma_
            # Additional safety: use inflect to singularize if needed
            singular = self.inflect_engine.singular_noun(lemma)
            tokens.append(singular if singular else lemma)
        return " ".join(tokens)

    def singularize(self, word: str) -> str:
        """Convert a single word to singular form."""
        if not word:
            return word
        singular = self.inflect_engine.singular_noun(word.lower())
        return singular if singular else word.lower()