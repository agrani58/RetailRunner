"""
spell_corrector.py — Smart spell correction for e-commerce product queries.

Uses a two-pass approach:
  1. Token-level correction: each word checked against known product vocabulary
  2. Phrase-level correction: whole query matched against known product phrases

This runs BEFORE NER so corrected text flows through the whole pipeline cleanly.
Logs the correction so the UI can show "Did you mean: ..." messages.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional, Any

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# ── Hard-coded high-priority product vocabulary (always available) ─────────────
# This is the base dictionary. It gets augmented dynamically from catalog at runtime.
PRODUCT_VOCAB: List[str] = [
    # Body/skin qualifiers
    "face", "hand", "hair", "body", "eye", "lip", "foot", "feet", "scalp", "beard", "nail",
    # Product types
    "cream", "wash", "gel", "serum", "spray", "stick", "mask", "scrub", "mist",
    "lotion", "foam", "powder", "balm", "wax", "shampoo", "conditioner", "toner",
    "cleanser", "moisturizer", "sunscreen", "oil", "soap", "deodorant", "wipes",
    # Skin care
    "aloe", "vera", "vitamin", "niacinamide", "hyaluronic", "retinol", "rosehip",
    "charcoal", "cucumber", "papaya", "green", "tea", "rose", "water",
    # Hair
    "argan", "onion", "keratin", "dandruff", "herbal",
    # Makeup
    "lipstick", "lipbalm", "foundation", "mascara", "blush", "highlighter",
    "eyeliner", "concealer", "eyeshadow", "primer", "contour",
    # Clothing
    "shirt", "tshirt", "tee", "jeans", "denim", "dress", "gown", "kurta",
    "kurti", "saree", "jacket", "coat", "blazer", "skirt", "trouser", "palazzo",
    "leggings", "hoodie", "sweater", "cardigan",
    # Footwear
    "shoe", "shoes", "boot", "boots", "sneaker", "sneakers", "sandal", "sandals",
    "loafer", "slipper", "heel", "heels",
    # Electronics
    "laptop", "phone", "iphone", "smartphone", "tablet", "ipad", "camera",
    "headphone", "earphone", "earbud", "speaker", "monitor", "keyboard", "mouse",
    "charger", "cable", "router", "television",
    # Brands
    "apple", "samsung", "sony", "dell", "logitech", "bose", "dyson", "philips",
    "bosch", "canon", "nikon", "nike", "adidas",
    # Common modifiers
    "anti", "pro", "ultra", "super", "mini", "maxi", "midi", "matte", "glossy",
    "waterproof", "wireless", "bluetooth", "smart", "organic", "natural",
    "herbal", "ayurvedic",
    # Actions (stripped but need correct spelling first)
    "buy", "want", "need", "get", "find", "show", "recommend",
]

# Words that should NEVER be spell-corrected (too short, context words, etc.)
NO_CORRECT = {
    "i", "a", "an", "the", "to", "for", "in", "on", "at", "by", "or", "and",
    "is", "are", "was", "be", "of", "me", "my", "we", "it", "its",
    "do", "did", "has", "had", "not", "no", "up",
    "usd", "rs", "gb", "tb", "mb", "ml", "kg", "g", "l",
    "spf", "spf30", "spf50", "bb", "cc",
}

# Minimum token length to attempt correction
MIN_CORRECT_LEN = 3

# Score thresholds
TOKEN_SCORE_THRESHOLD = 82   # for individual token correction
PHRASE_SCORE_THRESHOLD = 75  # for full phrase correction


class SpellCorrector:
    """
    Corrects misspelled product queries before they reach the NER pipeline.

    Usage:
        corrector = SpellCorrector()
        corrector.update_catalog(products)   # call after loading catalog
        corrected, was_changed = corrector.correct("i want to buy hai roli")
        # → ("i want to buy hair oil", True)
    """

    def __init__(self):
        # Will be populated from catalog on update_catalog() call
        self._product_names: List[str] = []          # full product names, lowercase
        self._product_words: List[str] = []          # individual meaningful words from catalog
        self._known_phrases: List[str] = []          # multi-word product phrases for phrase matching
        self._vocab: List[str] = list(set(PRODUCT_VOCAB))  # combined vocab

    def update_catalog(self, products: List[Dict[str, Any]]) -> None:
        """Rebuild vocabulary from product catalog. Call after loading/refreshing."""
        names = []
        words_set = set(PRODUCT_VOCAB)

        for p in products:
            name = p.get("name", "").lower().strip()
            cat  = p.get("category", "").lower().strip()
            ptype = p.get("product_type", "").lower().strip()

            if name:
                names.append(name)
                for w in name.split():
                    w_clean = re.sub(r"[^\w]", "", w)
                    if len(w_clean) >= MIN_CORRECT_LEN and w_clean not in NO_CORRECT:
                        words_set.add(w_clean)

            for token in (cat + " " + ptype).split():
                t = re.sub(r"[^\w]", "", token)
                if len(t) >= MIN_CORRECT_LEN:
                    words_set.add(t)

        self._product_names = sorted(set(names), key=len, reverse=True)
        self._product_words = sorted(words_set)
        self._vocab = self._product_words  # combined

        # Build known multi-word phrases for phrase-level matching
        phrases = set()
        for name in self._product_names:
            parts = name.split()
            if len(parts) >= 2:
                phrases.add(name)
                # Also add sub-phrases (last N words)
                for n in range(2, min(len(parts), 4)):
                    phrases.add(" ".join(parts[-n:]))
        self._known_phrases = sorted(phrases, key=len, reverse=True)

        logger.info(
            f"✅ SpellCorrector updated: {len(self._product_names)} product names, "
            f"{len(self._vocab)} vocab words"
        )

    def correct(self, query: str) -> Tuple[str, bool]:
        """
        Correct misspellings in query.

        Returns:
            (corrected_query, was_changed)
        """
        if not query or len(query.strip()) < 2:
            return query, False

        q = query.strip()

        # Step 1: Try to find a matching product name for the "product part" of query
        corrected, changed = self._correct_product_phrase(q)
        if changed:
            return corrected, True

        # Step 2: Token-by-token correction
        corrected, changed = self._correct_tokens(q)
        return corrected, changed

    def _correct_product_phrase(self, query: str) -> Tuple[str, bool]:
        """
        Try to match the non-intent part of the query against known product names.
        E.g., "i want to buy hai roli" → extract "hai roli" → match "hair oil"
        """
        if not self._product_names and not self._known_phrases:
            return query, False

        # Strip common intent prefixes
        intent_re = re.compile(
            r"^(?:i\s+)?(?:want|need|would like|'d like)\s+(?:to\s+)?(?:buy|purchase|get|find|see|order|have)?\s*",
            re.I
        )
        show_re = re.compile(
            r"^(?:show\s+me|find\s+me|get\s+me|give\s+me|search\s+for|look\s+for|please\s+)\s*",
            re.I
        )
        stripped = intent_re.sub("", query).strip()
        stripped = show_re.sub("", stripped).strip()

        if not stripped or stripped == query:
            # No prefix stripped — try full query against product names
            stripped = query

        # Also strip trailing constraint phrases
        stripped = re.sub(
            r"\s+(?:under|below|above|over|with|at)\s+(?:₹|\$|rs\.?)?\s*[\d,.]+.*$",
            "", stripped, flags=re.I
        ).strip()

        if not stripped or len(stripped) < 3:
            return query, False

        # --- Match the stripped portion against known product phrases ---
        # Use token_sort_ratio to handle word order differences
        all_phrases = self._known_phrases + self._product_names[:100]
        if not all_phrases:
            return query, False

        best = process.extractOne(
            stripped,
            all_phrases,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=PHRASE_SCORE_THRESHOLD,
        )

        if best:
            matched_phrase, score, _ = best
            # Only correct if the match is meaningfully different AND better
            if score >= PHRASE_SCORE_THRESHOLD and matched_phrase.lower() != stripped.lower():
                # Rebuild: replace the product part with corrected version
                # Find where stripped appears in original query
                prefix = query[: len(query) - len(stripped)].rstrip()
                if prefix:
                    corrected = f"{prefix} {matched_phrase}"
                else:
                    corrected = matched_phrase
                logger.info(
                    f"🔤 SpellCorrector phrase: '{stripped}' → '{matched_phrase}' "
                    f"(score={score})"
                )
                return corrected, True

        return query, False

    def _correct_tokens(self, query: str) -> Tuple[str, bool]:
        """
        Correct individual misspelled tokens in the query.
        Only corrects tokens that are clearly wrong (low match in vocab).
        """
        if not self._vocab:
            return query, False

        tokens = query.split()
        corrected_tokens = []
        changed = False

        # Build a sliding window for multi-token correction
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            tok_clean = re.sub(r"[^\w]", "", tok).lower()

            # Skip: too short, numeric, no-correct list, already in vocab
            if (len(tok_clean) < MIN_CORRECT_LEN
                    or tok_clean in NO_CORRECT
                    or re.match(r"^\d+", tok_clean)
                    or tok_clean in self._vocab):
                corrected_tokens.append(tok)
                i += 1
                continue

            # Try two-token phrase correction first (e.g., "hai roli" → "hair oil")
            if i + 1 < len(tokens):
                two_tok_raw = f"{tok} {tokens[i+1]}"
                two_tok = re.sub(r"[^\w ]", "", two_tok_raw).lower()
                best2 = process.extractOne(
                    two_tok,
                    self._known_phrases,
                    scorer=fuzz.ratio,
                    score_cutoff=TOKEN_SCORE_THRESHOLD,
                )
                if best2:
                    matched2, score2, _ = best2
                    logger.info(
                        f"🔤 SpellCorrector 2-token: '{two_tok}' → '{matched2}' "
                        f"(score={score2})"
                    )
                    corrected_tokens.append(matched2)
                    changed = True
                    i += 2
                    continue

            # Single token correction
            best = process.extractOne(
                tok_clean,
                self._vocab,
                scorer=fuzz.ratio,
                score_cutoff=TOKEN_SCORE_THRESHOLD,
            )
            if best:
                matched, score, _ = best
                if matched != tok_clean:
                    logger.info(
                        f"🔤 SpellCorrector token: '{tok_clean}' → '{matched}' "
                        f"(score={score})"
                    )
                    corrected_tokens.append(matched)
                    changed = True
                else:
                    corrected_tokens.append(tok)
            else:
                corrected_tokens.append(tok)
            i += 1

        return " ".join(corrected_tokens), changed

    def get_suggestion_text(self, original: str, corrected: str) -> str:
        """Generate a human-readable correction message for the UI."""
        return f"(Showing results for: '{corrected}')"