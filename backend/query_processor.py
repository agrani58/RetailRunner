import re
import logging
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz, process

from text_normalizer import TextNormalizer
from ner_model import MLNERModel
from price_rating_predictor import HybridConstraintPredictor

logger = logging.getLogger(__name__)


class QueryProcessor:
    # Enhanced category mapping with direct entries and common misspellings
    CATEGORY_MAPPING = {
        # Electronics
        "headphone": "headphones", "headphones": "headphones", "hedphones": "headphones",
        "earbud": "headphones", "earbuds": "headphones",
        "headset": "headphones", "airpods": "headphones",
        "smartphone": "smartphones", "smartphones": "smartphones",
        "phone": "smartphones", "phones": "smartphones",
        "iphone": "smartphones", "galaxy": "smartphones",
        "laptop": "laptops", "laptops": "laptops", "labtop": "laptops",
        "macbook": "laptops", "notebook": "laptops",
        "gaming laptop": "laptops", "gaming labtop": "laptops",
        "gaming laptops": "laptops",
        "tablet": "tablets", "tablets": "tablets",
        "ipad": "tablets",
        "camera": "cameras", "cameras": "cameras",
        "dslr": "cameras",
        "watch": "watches", "watches": "watches",
        "smartwatch": "watches", "smartwatches": "watches",
        # Gaming
        "gaming console": "gaming consoles", "console": "gaming consoles",
        "playstation": "gaming consoles", "xbox": "gaming consoles",
        "nintendo": "gaming consoles",
        "gaming accessory": "gaming accessories", "gaming accessories": "gaming accessories",
        "gaming mouse": "gaming accessories", "gaming keyboard": "gaming accessories",
        "gaming headset": "gaming accessories",
        # Clothing - Men
        "men's shirt": "shirts", "men shirt": "shirts",
        "formal shirt": "shirts", "dress shirt": "shirts",
        "oxford shirt": "shirts",
        "men's jeans": "jeans", "men jeans": "jeans",
        "denim jeans": "jeans", "jeenz": "jeans",
        "jeans": "jeans",
        "men's jacket": "jackets", "leather jacket": "jackets",
        "bomber jacket": "jackets",
        # Clothing - Women
        "women's dress": "dresses", "women dress": "dresses",
        "summer dress": "dresses", "evening gown": "dresses",
        "party dress": "dresses",
        # General clothing terms
        "dress": "dresses", "dresses": "dresses",
        "sweater": "sweaters", "sweaters": "sweaters",
        "shirt": "shirts", "shirts": "shirts",
        "jacket": "jackets", "jackets": "jackets", "jackt": "jackets",
        "hoodie": "hoodies", "hoodies": "hoodies",
        # Footwear
        "shoe": "footwear", "shoes": "footwear",
        "running shoe": "footwear", "running shoes": "footwear",
        "sneaker": "footwear", "sneakers": "footwear",
        "boot": "footwear", "boots": "footwear",
        "hiking boot": "footwear", "hiking boots": "footwear",
        # Cosmetics
        "lipstick": "makeup", "matte lipstick": "makeup",
        "mascara": "makeup", "eyeliner": "makeup",
        "foundation": "makeup",
        # Skincare
        "face wash": "skin care", "facewash": "skin care",
        "face cream": "skin care", "facecream": "skin care",
        "moisturizer": "skin care", "serum": "skin care",
        "sunscreen": "skin care", "spf": "skin care",
        # Ethnic Wear
        "kurta": "women ethnic wear", "ethnic wear": "women ethnic wear",
        "saree": "women ethnic wear", "anarkali": "women ethnic wear",
        "kurti": "women ethnic wear",
        # Kids
        "kids wear": "kids wear", "kids clothing": "kids wear",
        "baby clothing": "baby clothing",
    }

    # Subcategory keywords (e.g., for gaming laptops)
    SUBCATEGORY_KEYWORDS = {
        "gaming laptop": ["gaming", "rog", "legion", "katana", "victus", "zephyrus", "msi", "asus rog", "lenovo legion", "hp victus", "msi katana"],
        "hiking boots": ["hiking", "waterproof", "gore-tex"],
        "casual slip ons": ["casual", "slip on", "slip-ons"],
    }

    BRAND_KEYWORDS = {
        "apple": ["iphone", "macbook", "ipad", "apple watch", "apple", "airpods"],
        "samsung": ["samsung", "galaxy"],
        "google": ["google", "pixel"],
        "sony": ["sony", "playstation", "wh-1000xm"],
        "bose": ["bose", "quietcomfort"],
        "dell": ["dell", "xps"],
        "hp": ["hp"],
        "lenovo": ["lenovo", "thinkpad"],
        "logitech": ["logitech", "mx master"],
        "canon": ["canon"],
        "nike": ["nike"],
        "adidas": ["adidas"],
    }

    def __init__(self, ner_model: MLNERModel, products: List[Dict[str, Any]]):
        self.ner = ner_model
        self.products = products
        self.normalizer = TextNormalizer()

        self._build_product_vocabulary()
        self._build_brand_lookup()

        # ML‑based constraint predictor – will fail if model missing (no fallback)
        self.ml_predictor = HybridConstraintPredictor()
        logger.info("✅ Hybrid constraint predictor ready")

    def _build_product_vocabulary(self):
        self.product_names = []
        self.product_by_category = {}

        for p in self.products:
            name = p.get("name", "").lower().strip()
            cat = p.get("category", "").lower().strip()
            if name:
                self.product_names.append(name)
            if cat:
                if cat not in self.product_by_category:
                    self.product_by_category[cat] = []
                self.product_by_category[cat].append(p)

        self.product_names = list(set(self.product_names))
        logger.info(f"📂 Built category index with keys: {list(self.product_by_category.keys())}")

    def _build_brand_lookup(self):
        self.brand_lookup = {}
        for brand, keywords in self.BRAND_KEYWORDS.items():
            for kw in keywords:
                self.brand_lookup[kw] = brand

    def _map_to_category(self, text: str) -> Optional[str]:
        """Map normalized query text to a category using exact and fuzzy matching."""
        text_lower = text.lower()
        logger.info(f"🔍 Mapping text: '{text_lower}'")
        # Exact match in mapping keys
        for keyword, category in self.CATEGORY_MAPPING.items():
            if keyword in text_lower:
                logger.info(f"🔍 Exact mapped '{keyword}' to '{category}'")
                return category

        # Fuzzy match on longer words (>=4 chars)
        words = text_lower.split()
        for word in words:
            if len(word) < 4:
                continue
            match = process.extractOne(
                word,
                list(self.CATEGORY_MAPPING.keys()),
                scorer=fuzz.partial_ratio,   # better for substrings
                score_cutoff=60               # lower threshold for misspellings
            )
            if match:
                matched_word, score = match[0], match[1]
                logger.info(f"🔍 Fuzzy mapped '{word}' -> '{matched_word}' ({score})")
                return self.CATEGORY_MAPPING[matched_word]

        # Fallback: direct substring match against actual product categories
        if hasattr(self, 'product_by_category') and self.product_by_category:
            categories = list(self.product_by_category.keys())
            # Try to find any category that appears in the text
            for cat in categories:
                if cat in text_lower:
                    logger.info(f"🔍 Direct category substring match: '{cat}'")
                    return cat
            # Fuzzy match against categories
            match = process.extractOne(text_lower, categories, scorer=fuzz.partial_ratio, score_cutoff=70)
            if match:
                matched_cat = match[0]
                logger.info(f"🔍 Fuzzy matched to actual category: '{matched_cat}'")
                return matched_cat

        logger.info("🔍 No category mapping found")
        return None

    def _extract_brand(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for kw, brand in self.brand_lookup.items():
            if kw in text_lower:
                logger.info(f"🏷️ Brand match: '{kw}' -> '{brand}'")
                return brand
        return None

    def _extract_subcategory_keywords(self, text: str) -> List[str]:
        text_lower = text.lower()
        keywords = []
        for subcat, kw_list in self.SUBCATEGORY_KEYWORDS.items():
            if subcat in text_lower:
                logger.info(f"🎮 Subcategory '{subcat}' detected, adding keywords: {kw_list}")
                keywords.extend(kw_list)
        return list(set(keywords))

    def process(self, query: str) -> Dict[str, Any]:
        original = query.strip()
        # Normalize a copy for category/brand mapping (remove stopwords, lemmatize)
        normalized_for_mapping = self.normalizer.normalize(original, for_semantic=True)

        # Extract category using normalized text
        search_category = self._map_to_category(normalized_for_mapping)

        # Extract brand (still works with normalized)
        brand = self._extract_brand(normalized_for_mapping)

        # Extract subcategory keywords (from original, but normalized may also work)
        subcategory_keywords = self._extract_subcategory_keywords(original)

        # Get constraints from the hybrid predictor (uses original query to preserve price words)
        constraints = self.ml_predictor.predict(original)

        logger.info(f"📝 Final: category={search_category}, brand={brand}, subcategory_keywords={subcategory_keywords}, constraints={constraints}")

        return {
            "original": original,
            "normalized": normalized_for_mapping,
            "brand": brand,
            "search_category": search_category,
            "subcategory_keywords": subcategory_keywords,
            "constraints": constraints,
        }