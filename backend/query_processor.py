import re
import logging
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz, process

from text_normalizer import TextNormalizer, nlp  # shared spaCy model
from ner_model import MLNERModel

logger = logging.getLogger(__name__)


class QueryProcessor:
    # Words that should NEVER be corrected (attribute keywords)
    PROTECTED_WORDS = {
        # Rating related
        "rating", "ratings", "rated", "rate", "reviews", "review", 
        "best", "top", "highest", "high", "better", "good", "great", "excellent",
        "worst", "bad", "poor", "lowest", "least", "minimum", "maximum",
        # Price related
        "cheapest", "cheap", "expensive", "price", "prices", "cost",
        "lowest", "low", "least", "most", "under", "over", "above", "below",
        "budget", "affordable", "premium", "luxury", "reasonable",
        # Quality related
        "durable", "sturdy", "quality", "reliable", "perfect",
        # General
        "with", "and", "for", "the", "a", "an", "find", "show", "me",
        "want", "need", "looking", "get", "buy", "purchase",
        # Added to preserve rating phrases
        "atleast", "atmost",
    }

    # Common product terms (these ARE product names, not attributes)
    COMMON_PRODUCT_TERMS = {
        # Footwear
        "shoes", "sneakers", "boots", "sandals", "flats", "heels", "loafers", "footwear",
        # Tops & jackets
        "jacket", "jackets", "coat", "coats", "hoodie", "sweater", "sweaters",
        "shirt", "shirts", "t-shirt", "tshirt", "blouse", "top",
        # Bottoms
        "pants", "jeans", "trousers", "shorts", "skirt", "skirts", "dress", "dresses",
        # Bags
        "bag", "bags", "backpack", "backpacks", "purse", "tote", "duffel",
        # Beauty & personal care
        "lipstick", "lipbalm", "lip balm", "sunscreen", "spf",
        "shampoo", "conditioner", "mask", "cream", "lotion", "serum",
        "face wash", "facewash", "body wash", "hair oil",
        # Electronics
        "laptop", "laptops", "phone", "phones", "tablet", "tablets", 
        "headphones", "speaker", "speakers", "watch", "watches",
        "smartwatch", "smartwatches",
    }

    # Static brand keywords
    BRAND_KEYWORDS = {
        "apple": ["iphone", "macbook", "ipad", "apple watch", "apple"],
        "samsung": ["samsung", "galaxy"],
        "hp": ["hp", "hewlett packard"],
        "dell": ["dell"],
        "lenovo": ["lenovo", "thinkpad"],
        "asus": ["asus", "rog"],
        "msi": ["msi"],
        "sony": ["sony", "playstation"],
        "microsoft": ["microsoft", "xbox", "surface"],
        "nintendo": ["nintendo"],
        "google": ["google", "pixel"],
        "oneplus": ["oneplus"],
        "xiaomi": ["xiaomi", "redmi"],
        "nothing": ["nothing"],
        "nike": ["nike"],
        "adidas": ["adidas"],
        "puma": ["puma"],
    }

    def __init__(self, ner_model: MLNERModel, products: List[Dict[str, Any]]):
        self.ner = ner_model
        self.products = products
        self.normalizer = TextNormalizer()

        # Build vocabulary for spelling correction (only product names)
        self.product_names = []
        self.product_terms = set()  # All product-related terms

        # Add product names
        for p in products:
            name = p.get("name", "").lower().strip()
            if name:
                self.product_names.append(name)
                self.product_terms.add(name)
                # Add individual words from product names (for partial matching)
                for word in name.split():
                    if len(word) >= 3 and word not in self.PROTECTED_WORDS:
                        # Check if it's not a number
                        if not word.replace('.', '').isdigit():
                            self.product_terms.add(word)

            # Add category and product type
            cat = p.get("category", "").lower().strip()
            if cat:
                self.product_terms.add(cat)
                for word in cat.split():
                    if len(word) >= 3 and word not in self.PROTECTED_WORDS:
                        if not word.replace('.', '').isdigit():
                            self.product_terms.add(word)

            ptype = p.get("product_type", "").lower().strip()
            if ptype:
                self.product_terms.add(ptype)
                for word in ptype.split():
                    if len(word) >= 3 and word not in self.PROTECTED_WORDS:
                        if not word.replace('.', '').isdigit():
                            self.product_terms.add(word)

        # Add common product terms
        for term in self.COMMON_PRODUCT_TERMS:
            self.product_terms.add(term)
            for word in term.split():
                if len(word) >= 3 and word not in self.PROTECTED_WORDS:
                    if not word.replace('.', '').isdigit():
                        self.product_terms.add(word)

        self.product_names = list(set(self.product_names))
        self.product_terms = list(self.product_terms)
        self.product_terms_set = set(self.product_terms)

        logger.info(f"📚 Built product vocabulary: {len(self.product_names)} product names, "
                    f"{len(self.product_terms)} total terms")

        # Build reverse brand lookup
        self.brand_lookup = {}
        for brand, keywords in self.BRAND_KEYWORDS.items():
            for kw in keywords:
                self.brand_lookup[kw] = brand

    # ------------------------------------------------------------------
    # 🔤 SMART SPELLING CORRECTION - Prioritise protected words
    # ------------------------------------------------------------------
    def _correct_spelling(self, text: str) -> str:
        """Only correct words that look like misspelled product names or attribute words."""
        if not text or len(text) < 3:
            return text

        words = text.lower().split()
        corrected_words = []

        for word in words:
            # Never correct protected words if already correct
            if word in self.PROTECTED_WORDS:
                corrected_words.append(word)
                continue

            # Skip numbers
            if word.replace('.', '').isdigit():
                corrected_words.append(word)
                continue

            # Skip short words
            if len(word) < 3:
                corrected_words.append(word)
                continue

            # First, check against protected words (lower threshold)
            protected_match = process.extractOne(
                word,
                self.PROTECTED_WORDS,
                scorer=fuzz.ratio,
                score_cutoff=70
            )
            if protected_match:
                matched_word, score, _ = protected_match
                logger.info(f"🔤 Protected word correction: '{word}' -> '{matched_word}' (score={score})")
                corrected_words.append(matched_word)
                continue

            # Then check if it's already a known product term
            if word in self.product_terms_set:
                corrected_words.append(word)
                continue

            # Try to find close match in product terms (threshold 80)
            match = process.extractOne(
                word,
                self.product_terms,
                scorer=fuzz.ratio,
                score_cutoff=75   # lower cutoff to get candidates, then filter
            )
            if match:
                matched_word, score, _ = match
                if score >= 80 and matched_word not in self.PROTECTED_WORDS:
                    if not matched_word.replace('.', '').isdigit():
                        logger.info(f"🔤 Spelling correction: '{word}' -> '{matched_word}' (score={score})")
                        corrected_words.append(matched_word)
                    else:
                        corrected_words.append(word)
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)

        return " ".join(corrected_words)

    # ------------------------------------------------------------------
    # 💰 PRICE CONSTRAINT EXTRACTION – requires explicit currency indicator
    # ------------------------------------------------------------------
    def _extract_price_constraints(self, text: str) -> Dict[str, Any]:
        """
        Extract price constraints only when the number is accompanied by
        a dollar sign ($), the word 'dollar(s)', or 'price'.
        This prevents misinterpreting ratings (e.g., "above 4.8") as prices.
        """
        constraints = {}
        text_lower = text.lower()

        # Patterns that require a dollar sign or the word 'dollar(s)' or 'price'
        price_patterns = [
            # under $50, under 50 dollars, under 50 price
            (r'(?:under|less than|below|max(?:imum)?(?:\s+price)?)\s+\$?(\d+(?:\.\d+)?)(?:\s+dollars?|\s+price\b)', 'max'),
            # over $50, over 50 dollars, over 50 price
            (r'(?:over|above|more than|min(?:imum)?(?:\s+price)?)\s+\$?(\d+(?:\.\d+)?)(?:\s+dollars?|\s+price\b)', 'min'),
            # between $50 and $100, between 50 and 100 dollars
            (r'between\s+\$?(\d+(?:\.\d+)?)\s+and\s+\$?(\d+(?:\.\d+)?)(?:\s+dollars?)?\b', 'between'),
            # explicit $50 (dollar sign alone) - we'll ignore for now
        ]

        for pattern, typ in price_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                if typ == 'max':
                    constraints['price_max'] = float(match.group(1)) * 100
                elif typ == 'min':
                    constraints['price_min'] = float(match.group(1)) * 100
                elif typ == 'between':
                    constraints['price_min'] = float(match.group(1)) * 100
                    constraints['price_max'] = float(match.group(2)) * 100

        return constraints

    # ------------------------------------------------------------------
    # ⭐ RATING CONSTRAINT EXTRACTION – handles all rating phrases
    # ------------------------------------------------------------------
    def _extract_rating_constraints(self, text: str) -> Dict[str, Any]:
        """
        Extract rating constraints like:
        - rated above 4.5
        - above 4.5
        - 4.5 stars and above
        - > 4.5
        - 4.5+ rating
        - minimum rating 4.5
        - rating 4.6
        - rated 4.9
        - at least 4.5, atleast 4.5, rating at least 4.5, rating atleast 4.5, etc.
        - rating at least of 4.5 (with optional "of")
        - at most 4.5, atmost 4.5, rating at most 4.5, etc. (inclusive maximum)
        Only numbers between 0 and 5 (inclusive) are considered valid ratings.
        Uses a small epsilon for exclusive comparisons.
        """
        constraints = {}
        text_lower = text.lower()
        EPS = 0.001   # small offset for exclusive comparisons

        rating_patterns = [
            # "above rating 4.5", "above 4.5" (exclusive)
            (r'(?:above|over|>|>=|≥|greater than|more than)\s+(?:rating\s+)?(\d+(?:\.\d+)?)', True, True),
            (r'(?:below|under|<|<=|≤|less than)\s+(?:rating\s+)?(\d+(?:\.\d+)?)', False, True),
            # "rating above 4.5", "rated above 4.5"
            (r'(?:rated|rating)\s+(?:above|over|>|>=|≥|greater than|more than)\s+(\d+(?:\.\d+)?)', True, True),
            (r'(?:rated|rating)\s+(?:below|<|<=|≤|less than)\s+(\d+(?:\.\d+)?)', False, True),
            # "4.5+" inclusive
            (r'(\d+(?:\.\d+)?)\s*\+\s*(?:stars?|rating)', True, False),
            # "4.5 and above" inclusive
            (r'(\d+(?:\.\d+)?)\s*(?:stars?|rating)\s*(?:and above|or higher|or more)', True, False),
            # "at least 4.5", "atleast 4.5", and variations with optional "of"
            (r'(?:at\s+least|atleast)\s+(?:rating\s+)?(?:of\s+)?(\d+(?:\.\d+)?)', True, False),
            (r'(?:rating|rated)\s+(?:at\s+least|atleast)\s+(?:of\s+)?(\d+(?:\.\d+)?)', True, False),
            # "at most 4.5", "atmost 4.5" (inclusive maximum)
            (r'(?:at\s+most|atmost)\s+(?:rating\s+)?(?:of\s+)?(\d+(?:\.\d+)?)', False, False),
            (r'(?:rating|rated)\s+(?:at\s+most|atmost)\s+(?:of\s+)?(\d+(?:\.\d+)?)', False, False),
            # "minimum rating 4.5" inclusive
            (r'(?:minimum|min)\s*(?:rating|stars?)\s*(?:of)?\s*(\d+(?:\.\d+)?)', True, False),
            (r'(?:maximum|max)\s*(?:rating|stars?)\s*(?:of)?\s*(\d+(?:\.\d+)?)', False, False),
            # "rating 4.6" inclusive
            (r'(?:rated|rating)\s*[:\s]*(\d+(?:\.\d+)?)', True, False),
        ]

        for pattern, is_min, exclusive in rating_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                num_str = match.group(1)
                if not num_str:
                    continue
                try:
                    val = float(num_str)
                except ValueError:
                    continue
                if 0 <= val <= 5:
                    if is_min:
                        constraints['rating_min'] = val + (EPS if exclusive else 0)
                    else:
                        constraints['rating_max'] = val - (EPS if exclusive else 0)
                    logger.info(f"📊 Extracted {'min' if is_min else 'max'}: {val} "
                                f"{'(exclusive)' if exclusive else '(inclusive)'}")

        return constraints

    # ------------------------------------------------------------------
    # 🔽 SORT PREFERENCE EXTRACTION – now includes "least rating", "lowest rating", etc.
    # ------------------------------------------------------------------
    def _extract_sort_preferences(self, text: str) -> Dict[str, str]:
        """Extract sorting preferences (highest rating, cheapest, etc.)"""
        preferences = {}
        text_lower = text.lower()
        
        # Rating preferences – descending (best/highest/maximum)
        if re.search(r'\b(highest rating|best rating|best rated|top rated|best reviews|best|maximum rating)\b', text_lower):
            preferences['rating_sort'] = 'desc'
        # Rating preferences – ascending (lowest/least/minimum/worst)
        elif re.search(r'\b(lowest rating|least rating|minimum rating|worst rating|worst rated|lowest rated|least rated|minimum rated)\b', text_lower):
            preferences['rating_sort'] = 'asc'
        
        # Price preferences
        if re.search(r'\b(cheapest|lowest price|most affordable|budget)\b', text_lower):
            preferences['price_sort'] = 'asc'
        elif re.search(r'\b(most expensive|highest price|premium|luxury)\b', text_lower):
            preferences['price_sort'] = 'desc'
        
        return preferences
    # ------------------------------------------------------------------
    # 🔍 MAIN PROCESSING
    # ------------------------------------------------------------------
    def process(self, query: str) -> Dict[str, Any]:
        original = query.strip()
        normalized = self.normalizer.normalize(original)
        lemmatized_full = self.normalizer.lemmatize(original)

        # Apply spelling correction (now prioritises protected words)
        corrected = self._correct_spelling(original)
        
        # For NER, remove attribute words but keep numbers that might be part of product names (like "iPhone 15")
        words = corrected.split()
        filtered_for_ner = []
        for w in words:
            # Keep numbers (they might be part of product names like "iPhone 15")
            if w.replace('.', '').isdigit():
                # Check if it's likely a rating (between 1 and 5)
                try:
                    num = float(w)
                    if 1 <= num <= 5:
                        # This is probably a rating, don't include in NER
                        continue
                except:
                    pass
                filtered_for_ner.append(w)
            elif w not in self.PROTECTED_WORDS:
                filtered_for_ner.append(w)
        
        text_for_ner = " ".join(filtered_for_ner) if filtered_for_ner else corrected
        
        # Extract product entities
        ner_result = self.ner.extract(text_for_ner)
        raw_entities = [e["text"] for e in ner_result.get("products", [])]

        # Fallback entity extraction (only if NER found nothing)
        if not raw_entities:
            doc = nlp(text_for_ner.lower())
            for token in doc:
                if token.pos_ in ("NOUN", "PROPN") and len(token.text) >= 3:
                    if token.text.lower() in self.COMMON_PRODUCT_TERMS:
                        raw_entities.append(token.text.lower())
                        logger.info(f"🧠 Fallback entity: '{token.text}'")
            if raw_entities:
                raw_entities = list(set(raw_entities))

        # Clean entities - remove any that are just numbers or protected words
        cleaned_entities = []
        for ent in raw_entities:
            if ent and not ent.replace('.', '').isdigit() and ent not in self.PROTECTED_WORDS:
                cleaned_entities.append(ent)
        
        lemmatised_entities = list({
            self.normalizer.lemmatize(ent) for ent in cleaned_entities if ent
        })

        # Brand detection
        brand = None
        query_lower = original.lower()
        for kw, brand_name in self.brand_lookup.items():
            if kw in query_lower:
                brand = brand_name
                logger.info(f"🏷️ Detected brand: {brand}")
                break

        # Fuzzy exact-product match
        exact_match = None
        candidates_to_try = [
            corrected,
            normalized,
            lemmatized_full,
            " ".join(cleaned_entities) if cleaned_entities else None
        ]
        
        for candidate in candidates_to_try:
            if not candidate or len(candidate) < 3:
                continue
            result = process.extractOne(
                candidate,
                self.product_names,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=75
            )
            if result:
                exact_match = result[0]
                logger.info(f"🔍 Fuzzy product match: '{candidate}' -> '{exact_match}' (score={result[1]})")
                break

        # Extract constraints and preferences from the corrected query (so that fixed spelling works)
        price_constraints = self._extract_price_constraints(corrected)
        rating_constraints = self._extract_rating_constraints(corrected)
        sort_preferences = self._extract_sort_preferences(corrected)
        
        # Combine
        constraints = {**price_constraints, **rating_constraints, **sort_preferences}

        return {
            "original": original,
            "corrected": corrected,
            "normalized": normalized,
            "lemmatized": lemmatized_full,
            "product_entities": lemmatised_entities,
            "product_entities_raw": cleaned_entities,
            "brand": brand,
            "exact_product_match": exact_match,
            "keywords": normalized.split(),
            "constraints": constraints,
        }