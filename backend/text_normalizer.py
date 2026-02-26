"""
text_normalizer.py  — v2
Lightweight, dependency-minimal normalizer.
Uses spaCy for lemmatization only; inflect for singular safety.
"""

import re
import inflect
import spacy


class TextNormalizer:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        except OSError:
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
        self.inflect_engine = inflect.engine()

    def normalize(self, text: str, for_semantic: bool = True) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""
        doc = self.nlp(text.lower())
        tokens = []
        for token in doc:
            if token.is_punct or token.is_space:
                continue
            if for_semantic and token.is_stop:
                continue
            lemma = token.lemma_
            singular = self.inflect_engine.singular_noun(lemma)
            tokens.append(singular if singular else lemma)
        return " ".join(tokens)

    def singularize(self, word: str) -> str:
        if not word or not isinstance(word, str):
            return ""
        word_lower = word.lower().strip()
        singular = self.inflect_engine.singular_noun(word_lower)
        return singular if singular else word_lower