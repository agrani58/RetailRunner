import re
import logging
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz, process

from text_normalizer import TextNormalizer, nlp  # shared spaCy model
from ner_model import MLNERModel

logger = logging.getLogger(__name__)


class QueryProcessor:
    # ------------------------------------------------------------------
    # 🛡️ Common product terms – NEVER correct these single words
    #    (they are valid generic product names)
    # ------------------------------------------------------------------
    COMMON_PRODUCT_TERMS = {
        # Footwear
        "shoes", "sneakers", "boots", "sandals", "flats", "heels", "loafers",
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
        "face wash", "facewash", "body wash",
        # Electronics
        "laptop", "phone", "tablet", "headphones", "speaker", "watch",
        # Add any other common terms you want to protect
    }

    # Static brand keywords – one‑time setup, not per product.
    BRAND_KEYWORDS = {
        "apple": ["iphone", "macbook", "ipad", "apple watch", "apple"],
        "samsung": ["samsung", "galaxy"],
        "hp": ["hp", "hewlett packard"],
        "dell": ["dell"],
        "lenovo": ["lenovo", "thinkpad"],
        "asus": ["asus", "rog"],
        "msi": ["msi"],
        "sony": ["sony", "playstation"],
        "microsoft": ["microsoft", "xbox"],
        "nintendo": ["nintendo"],
        "google": ["google", "pixel"],
        "oneplus": ["oneplus"],
        "xiaomi": ["xiaomi", "redmi"],
        "nothing": ["nothing"],
    }

    def __init__(self, ner_model: MLNERModel, products: List[Dict[str, Any]]):
        self.ner = ner_model
        self.products = products
        self.normalizer = TextNormalizer()

        # ------------------------------------------------------------------
        # 🚀 Build vocabulary for spelling correction (dynamic)
        #    1. Full product names
        #    2. Single words from product names (≥3 chars, not stopwords)
        #    3. Categories and product types
        #    4. PLUS common product terms (to enable correction of e.g. "shoees")
        # ------------------------------------------------------------------
        self.all_terms = set()
        self.product_names = []
        self.single_words = set()          # for per‑word correction

        # ----- Add terms from product catalog -----
        for p in products:
            name = p.get("name", "").lower().strip()
            if name:
                self.product_names.append(name)
                self.all_terms.add(name)
                for word in name.split():
                    word = word.strip()
                    if len(word) >= 3 and word not in self.normalizer.stopwords:
                        self.all_terms.add(word)
                        self.single_words.add(word)

            cat = p.get("category", "").lower().strip()
            if cat:
                self.all_terms.add(cat)
                for word in cat.split():
                    if len(word) >= 3 and word not in self.normalizer.stopwords:
                        self.single_words.add(word)

            ptype = p.get("product_type", "").lower().strip()
            if ptype:
                self.all_terms.add(ptype)
                for word in ptype.split():
                    if len(word) >= 3 and word not in self.normalizer.stopwords:
                        self.single_words.add(word)

        # ----- Add common product terms to enable correction -----
        for term in self.COMMON_PRODUCT_TERMS:
            term_lower = term.lower()
            self.all_terms.add(term_lower)
            # Add individual words from multi‑word terms
            for word in term_lower.split():
                if len(word) >= 3 and word not in self.normalizer.stopwords:
                    self.single_words.add(word)

        self.product_names = list(set(self.product_names))
        self.all_terms = list(self.all_terms)
        self.single_words = list(self.single_words)
        self.single_words_set = set(self.single_words)   # fast membership

        logger.info(f"📚 Built spelling correction vocabulary: {len(self.all_terms)} total terms, "
                    f"{len(self.single_words)} single‑word terms (including common product terms)")

        # Build reverse brand lookup
        self.brand_lookup = {}
        for brand, keywords in self.BRAND_KEYWORDS.items():
            for kw in keywords:
                self.brand_lookup[kw] = brand

    # ------------------------------------------------------------------
    # 🔤 SPELLING CORRECTION – four‑stage fuzzy matching
    #    1. Full query vs product names (strict)
    #    2. Protect known product terms – return unchanged
    #    3. Full query vs single‑word vocabulary (broad)
    #    4. Per‑word correction (single words) with FILTER
    # ------------------------------------------------------------------
    def _correct_spelling(self, text: str) -> str:
        """Spell‑correct the query. Returns corrected text or original if no good match."""
        if not text or len(text) < 3:
            return text

        text_lower = text.lower().strip()
        words = text_lower.split()

        # ------------------------------------------------------------
        # Stage 1: Try full query against product names (high threshold)
        # ------------------------------------------------------------
        full_match = process.extractOne(
            text_lower,
            self.product_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=75
        )
        if full_match:
            match, score, _ = full_match
            logger.info(f"🔤 Spelling correction (full product): '{text}' -> '{match}' (score={score})")
            return match

        # ------------------------------------------------------------
        # Stage 2: If it's a single word AND it's a known common product term,
        #          DO NOT CORRECT – return as is.
        # ------------------------------------------------------------
        if len(words) == 1 and text_lower in self.COMMON_PRODUCT_TERMS:
            logger.debug(f"🔤 Skipping correction – '{text_lower}' is a known product term")
            return text_lower

        # ------------------------------------------------------------
        # Stage 3: Try full query against single‑word vocabulary (broad)
        #          Only if query is NOT already a known product word
        # ------------------------------------------------------------
        if len(words) == 1 and text_lower in self.single_words_set:
            logger.debug(f"🔤 Skipping broad vocab match – '{text_lower}' already in vocabulary")
        else:
            broad_match = process.extractOne(
                text_lower,
                self.single_words,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=70
            )
            if broad_match:
                match, score, _ = broad_match
                if len(match.split()) == 1:
                    logger.info(f"🔤 Spelling correction (broad vocab): '{text}' -> '{match}' (score={score})")
                    return match

        # ------------------------------------------------------------
        # Stage 4: Correct each word individually – WITH FILTER
        # ------------------------------------------------------------
        corrected_words = []
        for word in words:
            if len(word) < 3 or word in self.normalizer.stopwords:
                corrected_words.append(word)
                continue

            # If the word itself is a known product term, keep it (do not correct)
            if word in self.COMMON_PRODUCT_TERMS or word in self.single_words_set:
                corrected_words.append(word)
                continue

            word_match = process.extractOne(
                word.lower(),
                self.single_words,
                scorer=fuzz.ratio,
                score_cutoff=70
            )
            if word_match:
                match, score, _ = word_match
                # 🔥 FILTER: only accept corrections that are not stopwords,
                #            not digits, and at least 3 chars.
                if (match not in self.normalizer.stopwords and
                    not match.isdigit() and
                    len(match) >= 3):
                    logger.info(f"🔤 Spelling correction (word): '{word}' -> '{match}' (score={score})")
                    corrected_words.append(match)
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)

        return " ".join(corrected_words)

    def process(self, query: str) -> Dict[str, Any]:
        original = query.strip()
        normalized = self.normalizer.normalize(original)
        lemmatized_full = self.normalizer.lemmatize(original)

        # ------------------------------------------------------------------
        # 🔤 SPELLING CORRECTION – ALWAYS APPLY, use corrected for NER & search
        # ------------------------------------------------------------------
        corrected = self._correct_spelling(original)
        text_for_ner = corrected if corrected != original.lower() else original

        # 1️⃣ Extract & CLEAN product entities (using corrected text)
        ner_result = self.ner.extract(text_for_ner)
        raw_entities = [e["text"] for e in ner_result.get("products", [])]

        # ----------------------------------------------------------------
        # 🧠 FALLBACK: If NER found nothing, scan the query for known product nouns
        # ----------------------------------------------------------------
        if not raw_entities:
            doc = nlp(text_for_ner.lower())
            for token in doc:
                # Only nouns and proper nouns, length >= 3
                if token.pos_ in ("NOUN", "PROPN") and len(token.text) >= 3:
                    lemma = token.lemma_.lower()
                    # Check if the lemma or original word is in our vocabulary
                    if (lemma in self.single_words_set or 
                        token.text.lower() in self.single_words_set or
                        token.text.lower() in self.COMMON_PRODUCT_TERMS):
                        raw_entities.append(token.text.lower())
                        logger.info(f"🧠 Fallback entity extraction: '{token.text}' -> '{lemma}'")
            if raw_entities:
                raw_entities = list(set(raw_entities))  # deduplicate

        lemmatised_entities = list({
            self.normalizer.lemmatize(ent) for ent in raw_entities if ent
        })
        cleaned_entities = list({self._clean_entity(ent) for ent in raw_entities})

        # 2️⃣ Brand detection
        brand = None
        query_lower = original.lower()
        for kw, brand_name in self.brand_lookup.items():
            if kw in query_lower:
                brand = brand_name
                break

        # 3️⃣ Fuzzy exact‑product match (try normalized, lemmatised, corrected)
        exact_match = None
        candidates_to_try = [normalized, lemmatized_full, corrected]
        for candidate in candidates_to_try:
            if not candidate:
                continue
            result = process.extractOne(
                candidate,
                self.product_names,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=70
            )
            if result:
                exact_match = result[0]
                logger.info(f"🔍 Fuzzy product match: '{candidate}' -> '{exact_match}'")
                break

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
        }

    @staticmethod
    def _clean_entity(entity: str) -> str:
        entity = entity.strip()
        entity = re.sub(r'[?!,.;:]+$', '', entity)
        return entity.lower()