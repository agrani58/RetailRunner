"""
query_processor.py – corrected version
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple

from rapidfuzz import fuzz, process

from text_normalizer import TextNormalizer
from ner_model import MLNERModel, _normalize_plural
from recommendation_model import RecommendationModel
from spell_corrector import SpellCorrector

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# TIER 1: BROWSE aliases — bare/generic words → whole category
# ─────────────────────────────────────────────────────────────
BROWSE_SYNONYMS: Dict[str, str] = {
    # Electronics
    "tv": "televisions", "telly": "televisions", "television": "televisions",
    "phone": "smartphones", "phones": "smartphones", "mobile": "smartphones",
    "smartphone": "smartphones", "cellphone": "smartphones",
    "laptop": "laptops", "laptops": "laptops",
    "notebook": "laptops", "notebooks": "laptops",
    "macbook": "laptops", "chromebook": "laptops",
    "headphone": "headphones", "headphones": "headphones",
    "earphone": "headphones", "earphones": "headphones",
    "earbud": "headphones", "earbuds": "headphones",
    "airpod": "headphones", "airpods": "headphones", "headset": "headphones",
    "watch": "smartwatches", "smartwatch": "smartwatches",
    "tablet": "tablets", "tablets": "tablets", "ipad": "tablets",
    "camera": "cameras", "cameras": "cameras", "dslr": "cameras",
    "monitor": "monitors", "monitors": "monitors", "display": "monitors",
    "speaker": "speakers", "speakers": "speakers",
    # Apparel
    "tshirt": "t-shirts", "t-shirt": "t-shirts",
    "tee": "t-shirts", "tees": "t-shirts",
    "shirt": "t-shirts", "shirts": "t-shirts",
    # "sweater" moved to PRODUCT_SYNONYMS
    "shoe": "footwear", "shoes": "footwear",
    "sneaker": "footwear", "sneakers": "footwear",
    "boot": "footwear", "boots": "footwear",
    "sandal": "footwear", "sandals": "footwear",
    "footwear": "footwear",
    "jean": "jeans", "jeans": "jeans", "denim": "jeans",
    "dress": "dresses", "dresses": "dresses", "frock": "dresses",
    "gown": "dresses", "gowns": "dresses",
    "coat": "jackets", "coats": "jackets",
    "jacket": "jackets", "jackets": "jackets",
    "kurta": "women ethnic wear", "kurtis": "women ethnic wear", "kurti": "women ethnic wear",
    "saree": "women ethnic wear", "sarees": "women ethnic wear",
    "salwar": "women ethnic wear",
    # Skin care — bare words only (all specific terms moved to PRODUCT_SYNONYMS)
    # Personal care — bare words only
    "lotion": "personal care", "lotions": "personal care",
    "soap": "personal care", "soaps": "personal care",
    "deodorant": "personal care", "deodorants": "personal care",
    "wipes": "personal care",
    # Hair care — bare words only (shampoo, conditioner etc. moved to PRODUCT_SYNONYMS)
    # Makeup — bare words only (lipstick, foundation etc. moved to PRODUCT_SYNONYMS)
    # Gaming
    "console": "gaming consoles", "consoles": "gaming consoles",
    "playstation": "gaming consoles", "xbox": "gaming consoles",
    # Home
    "vacuum": "home appliances",
    "dumbbell": "fitness equipment", "dumbbells": "fitness equipment",
    "treadmill": "fitness equipment",
    "router": "networking hardware",
    # Category names themselves
    "skin care": "skin care", "skincare": "skin care",
    "hair care": "hair care", "haircare": "hair care",
    "personal care": "personal care",
    "makeup": "makeup", "cosmetics": "makeup",
    "televisions": "televisions",
    "smartphones": "smartphones",
    "gaming accessories": "gaming accessories",
    "gaming consoles": "gaming consoles",
    "home appliances": "home appliances",
    "fitness equipment": "fitness equipment",
    "office furniture": "office furniture",
    "networking hardware": "networking hardware",
    "photography accessories": "photography accessories",
    "car electronics": "car electronics",
    "security": "security",
    "software": "software",
    "accessories": "accessories",
    "kids wear": "kids wear",
    "baby clothing": "baby clothing",
    "women ethnic wear": "women ethnic wear",
}

# ─────────────────────────────────────────────────────────────
# TIER 2: PRODUCT aliases — specific phrases → filter within category
# ─────────────────────────────────────────────────────────────
PRODUCT_SYNONYMS: Dict[str, str] = {
    # ── Skin care specific products ───────────────────────────
    "face wash": "skin care",
    "face cream": "skin care",
    "face mask": "skin care",
    "face scrub": "skin care",
    "face mist": "skin care",
    "face gel": "skin care",
    "face pack": "skin care",
    "face oil": "skin care",
    "face serum": "skin care",
    "face toner": "skin care",
    "face cleanser": "skin care",
    "face moisturizer": "skin care",
    "face lotion": "skin care",
    "face powder": "skin care",
    "face spray": "skin care",
    "anti acne": "skin care",
    "anti aging": "skin care",
    "anti ageing": "skin care",
    "aloe vera": "skin care",
    "vitamin c": "skin care",
    "vitamin e": "skin care",
    "green tea": "skin care",
    "rose water": "skin care",
    "tea tree": "skin care",
    "niacinamide": "skin care",
    "hyaluronic acid": "skin care",
    "spf 30": "skin care",
    "spf 50": "skin care",
    "night cream": "skin care",
    "day cream": "skin care",
    "eye cream": "skin care",
    "eye gel": "skin care",
    "under eye": "skin care",
    "peel off mask": "skin care",
    "clay mask": "skin care",
    "papaya face pack": "skin care",
    "cucumber gel": "skin care",
    "rosehip": "skin care",
    "retinol": "skin care",
    # Single-word skin care terms (now here, not in BROWSE)
    "moisturizer": "skin care",
    "moisturiser": "skin care",
    "sunscreen": "skin care",
    "spf": "skin care",
    "serum": "skin care",
    "serums": "skin care",
    "toner": "skin care",
    "toners": "skin care",
    "cleanser": "skin care",
    "cleansers": "skin care",
    "cream": "skin care",
    "creams": "skin care",
    # ── Makeup specific products ──────────────────────────────
    "lipstick": "makeup",
    "lipsticks": "makeup",
    "lip balm": "personal care",
    "lip balms": "personal care",
    "foundation": "makeup",
    "mascara": "makeup",
    "blush": "makeup",
    "highlighter": "makeup",
    "concealer": "makeup",
    "eyeshadow": "makeup",
    "eyeliner": "makeup",
    "bb cream": "makeup",
    "cc cream": "makeup",
    "compact powder": "makeup",
    "waterproof mascara": "makeup",
    "eyeliner pen": "makeup",
    "matte lipstick": "makeup",
    "fixing spray": "makeup",
    "makeup fixing spray": "makeup",
    "highlighter stick": "makeup",
    "liquid foundation": "makeup",
    # ── Hair care specific products ───────────────────────────
    "shampoo": "hair care",
    "shampoos": "hair care",
    "conditioner": "hair care",
    "conditioners": "hair care",
    "hair oil": "hair care",
    "hair oils": "hair care",
    "hair serum": "hair care",
    "hair mask": "hair care",
    "hair cream": "hair care",
    "hair spray": "hair care",
    "hair gel": "hair care",
    "hair wax": "hair care",
    "hair conditioner": "hair care",
    "hair fall control": "hair care",
    "anti dandruff": "hair care",
    "anti dandruff shampoo": "hair care",
    "keratin shampoo": "hair care",
    "keratin conditioner": "hair care",
    "argan oil": "hair care",
    "argan hair oil": "hair care",
    "onion oil": "hair care",
    "onion hair oil": "hair care",
    "coconut oil": "hair care",
    "scalp detox": "hair care",
    "scalp scrub": "hair care",
    "herbal hair mask": "hair care",
    # ── Personal care specific products ───────────────────────
    "hand cream": "personal care",
    "hand creams": "personal care",
    "hand wash": "personal care",
    "hand lotion": "personal care",
    "hand sanitizer": "personal care",
    "body lotion": "personal care",
    "body wash": "personal care",
    "body cream": "personal care",
    "body scrub": "personal care",
    "body oil": "personal care",
    "body spray": "personal care",
    "body mist": "personal care",
    "foot cream": "personal care",
    "foot scrub": "personal care",
    "foot care": "personal care",
    "foot care cream": "personal care",
    "lip gloss": "personal care",
    "lip liner": "personal care",
    "lip oil": "personal care",
    "shower gel": "personal care",
    "bathing soap": "personal care",
    "bath soap": "personal care",
    "roll on": "personal care",
    "roll ons": "personal care",
    "roll-on": "personal care",
    "roll-ons": "personal care",
    "deodorant roll on": "personal care",
    "deodorant roll ons": "personal care",
    "deodorant stick": "personal care",
    "deodorant spray": "personal care",
    "beard oil": "personal care",
    "beard growth oil": "personal care",
    "intimate wash": "personal care",
    "makeup remover": "personal care",
    "makeup remover wipes": "personal care",
    # ── Dresses specific types ────────────────────────────────
    "maxi dress": "dresses",
    "maxi dresses": "dresses",
    "midi dress": "dresses",
    "midi dresses": "dresses",
    "mini dress": "dresses",
    "mini dresses": "dresses",
    "evening gown": "dresses",
    "evening gowns": "dresses",
    "summer dress": "dresses",
    "summer dresses": "dresses",
    "floral dress": "dresses",
    "wrap dress": "dresses",
    "shirt dress": "dresses",
    "sweater dress": "dresses",
    "knitted dress": "dresses",
    "bodycon dress": "dresses",
    "party dress": "dresses",
    "velvet gown": "dresses",
    "boho dress": "dresses",
    "sundress": "dresses",
    "pinafore dress": "dresses",
    "pleated dress": "dresses",
    "a-line dress": "dresses",
    # ADD SWEATER (SINGLE WORD) HERE – maps to dresses, will apply entity filter
    "sweater": "dresses",
    "sweaters": "dresses",
    # ── T-shirt specific types ────────────────────────────────
    "graphic tee": "t-shirts",
    "oversized tee": "t-shirts",
    "athletic tee": "t-shirts",
    "performance tee": "t-shirts",
    "v neck tee": "t-shirts",
    "v-neck tee": "t-shirts",
    "henley tee": "t-shirts",
    "tie dye tee": "t-shirts",
    "heavyweight tee": "t-shirts",
    "embroidered tee": "t-shirts",
    "vintage tee": "t-shirts",
    # ── Electronics specific ──────────────────────────────────
    "smart tv": "televisions",
    "oled tv": "televisions",
    "qled tv": "televisions",
    "gaming laptop": "laptops",
    "gaming laptops": "laptops",
    "gaming mouse": "gaming accessories",
    "gaming keyboard": "gaming accessories",
    "gaming headset": "gaming accessories",
    "wireless mouse": "accessories",
    "smart watch": "smartwatches",
    "smart watches": "smartwatches",
    "air fryer": "home appliances",
    # ── Footwear specific ─────────────────────────────────────
    "running shoes": "footwear",
    "running sneakers": "footwear",
    "chelsea boots": "footwear",
    "leather chelsea boots": "footwear",
    "platform loafers": "footwear",
    # ── Ethnic wear specific ──────────────────────────────────
    "printed kurta": "women ethnic wear",
    "embroidered kurta": "women ethnic wear",
    "silk kurta": "women ethnic wear",
    "cotton kurta": "women ethnic wear",
    "kurta set": "women ethnic wear",
    "kurta sets": "women ethnic wear",
    "tissue saree": "women ethnic wear",
}

# Combined for category inference
ALL_SYNONYMS: Dict[str, str] = {**BROWSE_SYNONYMS, **PRODUCT_SYNONYMS}

STOP_ENTITIES = {
    "nice", "good", "best", "great", "deal", "cool", "new", "cheap", "expensive",
    "long", "short", "least", "most", "high", "low", "value", "quality", "budget",
    "affordable", "premium", "top", "less", "more", "better", "worst", "popular",
    "rated", "review", "reviews", "price", "prices", "rating", "ratings", "stars",
    "buy", "purchase", "get", "want", "wanna", "need", "looking", "show",
    "find", "recommend", "search", "something", "anything", "product", "item",
    "products", "items",
}

BRAND_PATTERNS: Dict[str, List[str]] = {
    "apple":   ["iphone", "macbook", "ipad", "airpods", "apple watch"],
    "samsung": ["samsung", "galaxy"],
    "google":  ["google", "pixel"],
    "sony":    ["sony", "playstation"],
    "bose":    ["bose", "quietcomfort"],
    "dell":    ["dell", "xps"],
    "hp":      ["hp"],
    "lenovo":  ["lenovo", "thinkpad"],
    "nike":    ["nike"],
    "adidas":  ["adidas"],
    "oneplus": ["oneplus"],
    "logitech": ["logitech", "mx master"],
    "razer":   ["razer", "blackwidow"],
    "steelseries": ["steelseries", "rival"],
}

SORT_OVERRIDES: Dict[str, tuple] = {
    "cheapest":            ("price", "asc"),
    "least expensive":     ("price", "asc"),
    "most expensive":      ("price", "desc"),
    "best rated":          ("rating", "desc"),
    "highest rated":       ("rating", "desc"),
    "lowest rated":        ("rating", "asc"),
    "worst rated":         ("rating", "asc"),
    "with highest rating": ("rating", "desc"),
    "with best rating":    ("rating", "desc"),
    "top rated":           ("rating", "desc"),
}


class QueryProcessor:
    def __init__(
        self,
        ner_model: MLNERModel,
        products: List[Dict[str, Any]],
        rec_model: RecommendationModel,
    ):
        self.ner        = ner_model
        self.rec_model  = rec_model
        self.normalizer = TextNormalizer()

        # Spell corrector — auto-updated from catalog
        self.spell_corrector = SpellCorrector()

        if hasattr(self.ner, "update_catalog"):
            self.ner.update_catalog(products)

        self._categories: Dict[str, List[Dict]] = {}
        for p in products:
            cat = p.get("category", "").lower().strip()
            if cat:
                self._categories.setdefault(cat, []).append(p)
        self._cat_names: List[str] = list(self._categories.keys())

        # All product names for direct matching
        self._product_names: List[str] = [
            p.get("name", "").lower() for p in products if p.get("name")
        ]

        # Build synonym lookups
        self._syn: Dict[str, str] = {}
        for alias, canonical in ALL_SYNONYMS.items():
            self._syn[alias.lower()] = canonical.lower()
        for cat in self._cat_names:
            self._syn[cat] = cat
            if cat.endswith("s"):
                self._syn[cat[:-1]] = cat

        # Product alias lookup set
        self._product_alias_set: Set[str] = {k.lower() for k in PRODUCT_SYNONYMS}
        # Browse alias lookup set
        self._browse_alias_set: Set[str] = {k.lower() for k in BROWSE_SYNONYMS}

        # Update spell corrector with catalog
        self.spell_corrector.update_catalog(products)

        # Auto-expand synonyms from catalog (dynamic scalability)
        self._expand_synonyms_from_catalog(products)

        logger.info(
            f"✅ QueryProcessor ready – {len(products)} products, "
            f"{len(self._cat_names)} categories, "
            f"{len(self._product_alias_set)} product aliases, "
            f"{len(self._browse_alias_set)} browse aliases"
        )

    def _expand_synonyms_from_catalog(self, products: List[Dict[str, Any]]) -> None:
        """
        Auto-generate synonyms from product catalog.
        This makes the system scalable: any new product added to the API
        automatically gets recognized without code changes.
        """
        for p in products:
            name = p.get("name", "").lower().strip()
            cat  = p.get("category", "").lower().strip()

            if not name or not cat:
                continue

            # Full product name → its category (as a product synonym → filter ON)
            if name not in self._product_alias_set and name not in self._browse_alias_set:
                self._product_alias_set.add(name)
                self._syn[name] = cat

            # Also add product_type as browse synonym if it maps to a known category
            ptype = p.get("product_type", "").lower().strip()
            if ptype and ptype not in self._browse_alias_set and ptype != cat:
                # Only add as browse if it's a generic type word (single word)
                if " " not in ptype and len(ptype) >= 3:
                    self._browse_alias_set.add(ptype)
                    self._syn[ptype] = cat

        logger.info(
            f"📚 After auto-expansion: {len(self._product_alias_set)} product aliases"
        )

    # ─────────────────────────────────────────────────────────
    # Public
    # ─────────────────────────────────────────────────────────

    def process(self, query: str) -> Dict[str, Any]:
        logger.info(f"🔧 QueryProcessor.process called with: '{query}'")
        original   = query.strip()
        normalized = self.normalizer.normalize(original, for_semantic=True)

        # ── Spell correction (pre-NER) ──────────────────────────────────────
        corrected_query, was_corrected = self.spell_corrector.correct(original)
        if was_corrected:
            logger.info(f"✏️  Spell corrected: '{original}' → '{corrected_query}'")

        # Use corrected query for NER and category inference
        query_for_processing = corrected_query if was_corrected else original

        # ── NER ─────────────────────────────────────────────────────────────
        ner_results = self.ner.extract(query_for_processing)
        entities    = [e["text"] for e in ner_results.get("products", [])]
        logger.info(f"🧠 NER extracted product entities: {entities}")

        entities = self._clean_entities(entities)
        logger.info(f"🧹 After cleaning: {entities}")

        exclude_terms = self._extract_negations(original)

        # ── Constraints (price, rating) ─────────────────────────────────────
        rec         = self.rec_model.predict(original)
        constraints = rec["constraints"]
        filter_cat  = rec["filter_category"]
        sort_type   = rec["sort_type"]
        sort_dir    = rec["sort_dir"]

        explicit_sort = self._explicit_sort(original)
        if explicit_sort:
            sort_key, sort_val = explicit_sort
            for k in list(constraints.keys()):
                if k.endswith("_sort"):
                    del constraints[k]
            constraints[sort_key] = sort_val
            sort_type = "price" if sort_key == "price_sort" else "rating"
            sort_dir  = sort_val

        brand = self._extract_brand(original)
        search_category = self._infer_category(query_for_processing, entities)

        if search_category:
            logger.info(f"🔍 Category inferred: '{search_category}'")
        else:
            logger.info("⚠️ No category inferred from entities")

        skip_entity_filter, subcategory_keywords = self._decide_filter_strategy(
            query_for_processing, entities, search_category
        )

        if "price_sort" not in constraints and "rating_sort" not in constraints:
            if filter_cat == "price":
                val = "desc" if any(
                    w in original.lower() for w in ("expensive", "most")
                ) else "asc"
                constraints["price_sort"] = val
            elif filter_cat == "rating":
                constraints["rating_sort"] = "desc"

        # Build spell correction message for UI
        spell_suggestion = None
        if was_corrected:
            spell_suggestion = self.spell_corrector.get_suggestion_text(
                original, corrected_query
            )

        logger.info(
            f"📝 Final: category={search_category}, brand={brand}, "
            f"constraints={constraints}, entities={entities}, "
            f"skip_entity_filter={skip_entity_filter}, "
            f"subcategory_keywords={subcategory_keywords}"
        )

        return {
            "original":             original,
            "normalized":           normalized,
            "corrected_query":      corrected_query if was_corrected else None,
            "spell_suggestion":     spell_suggestion,
            "brand":                brand,
            "search_category":      search_category,
            "subcategory_keywords": subcategory_keywords,
            "constraints":          constraints,
            "product_entities":     entities,
            "exclude_terms":        exclude_terms,
            "sort_type":            sort_type,
            "sort_dir":             sort_dir,
            "skip_entity_filter":   skip_entity_filter,
        }

    # ─────────────────────────────────────────────────────────
    # Two-tier filter decision
    # ─────────────────────────────────────────────────────────

    def _decide_filter_strategy(
        self,
        query: str,
        entities: List[str],
        search_category: Optional[str],
    ) -> Tuple[bool, List[str]]:
        """
        Returns (skip_entity_filter: bool, subcategory_keywords: List[str]).

        SKIP = browse whole category (skip_entity_filter=True):
          - no entities at all
          - entity is a BROWSE alias (bare word like "shampoo", "gown", "lotion")
          - entity exactly equals the category name

        DON'T SKIP = filter within category (skip_entity_filter=False):
          - entity is a PRODUCT alias (specific phrase like "hand cream", "body lotion")
          - entity is a full product name from catalog
        """
        if not entities:
            logger.info("🔓 No entities → SKIP (browse category)")
            return True, []

        if not search_category:
            return False, []

        all_are_browse = True
        specific_entities = []

        for ent in entities:
            ent_lower   = ent.lower().strip()
            ent_singular = _normalize_plural(ent_lower)

            # Is it a specific PRODUCT alias or full product name?
            if (ent_lower in self._product_alias_set or
                    ent_singular in self._product_alias_set):
                logger.info(f"🎯 '{ent}' → PRODUCT alias → filter ON")
                all_are_browse = False
                specific_entities.append(ent_lower)
                continue

            # Is it a bare BROWSE alias or the category name itself?
            if (ent_lower == search_category or
                    ent_singular == search_category or
                    ent_lower in self._browse_alias_set or
                    ent_singular in self._browse_alias_set):
                logger.info(f"🔓 '{ent}' → BROWSE alias → skip filter")
                continue

            # Unknown entity → treat as specific qualifier → filter
            logger.info(f"🎯 '{ent}' → unregistered qualifier → filter ON")
            all_are_browse = False
            specific_entities.append(ent_lower)

        if all_are_browse:
            return True, []

        subcategory_keywords = self._build_subcategory_keywords(specific_entities)
        return False, subcategory_keywords

    def _build_subcategory_keywords(self, specific_entities: List[str]) -> List[str]:
        """Use full entity phrase as keyword — 'hand cream' not split into 'hand'+'cream'."""
        keywords = []
        seen = set()
        for ent in specific_entities:
            ent_l = ent.lower().strip()
            if ent_l not in seen:
                keywords.append(ent_l)
                seen.add(ent_l)
            singular = _normalize_plural(ent_l)
            if singular != ent_l and singular not in seen:
                keywords.append(singular)
                seen.add(singular)
        return keywords

    # ─────────────────────────────────────────────────────────
    # Category inference
    # ─────────────────────────────────────────────────────────

    def _infer_category(self, query: str, entities: List[str]) -> Optional[str]:
        q_lower = query.lower()

        # Longest-first synonym match
        for alias in sorted(ALL_SYNONYMS, key=len, reverse=True):
            idx = q_lower.find(alias)
            if idx == -1:
                continue
            end = idx + len(alias)
            if (idx == 0 or not q_lower[idx - 1].isalpha()) and \
               (end == len(q_lower) or not q_lower[end].isalpha()):
                canonical = ALL_SYNONYMS[alias]
                resolved  = self._resolve_to_catalog(canonical)
                if resolved:
                    logger.info(f"🔍 Synonym match: '{alias}' → '{resolved}'")
                    return resolved

        # Try singularized query
        q_singular = " ".join(_normalize_plural(tok) for tok in q_lower.split())
        if q_singular != q_lower:
            for alias in sorted(ALL_SYNONYMS, key=len, reverse=True):
                idx = q_singular.find(alias)
                if idx == -1:
                    continue
                end = idx + len(alias)
                if (idx == 0 or not q_singular[idx - 1].isalpha()) and \
                   (end == len(q_singular) or not q_singular[end].isalpha()):
                    canonical = ALL_SYNONYMS[alias]
                    resolved  = self._resolve_to_catalog(canonical)
                    if resolved:
                        logger.info(f"🔍 Synonym match (singular): '{alias}' → '{resolved}'")
                        return resolved

        # Dynamic synonym lookup (auto-expanded from catalog)
        for ent in entities:
            ent_l = ent.lower().strip()
            if ent_l in self._syn:
                cat = self._resolve_to_catalog(self._syn[ent_l])
                if cat:
                    logger.info(f"🔍 Dynamic syn: '{ent_l}' → '{cat}'")
                    return cat
            ent_s = _normalize_plural(ent_l)
            if ent_s in self._syn:
                cat = self._resolve_to_catalog(self._syn[ent_s])
                if cat:
                    logger.info(f"🔍 Dynamic syn (singular): '{ent_s}' → '{cat}'")
                    return cat

        # Entity progressive lookup
        for ent in entities:
            tokens = ent.lower().split()
            for start in range(len(tokens)):
                sub = " ".join(tokens[start:])
                if sub in self._categories:
                    return sub
                res = ALL_SYNONYMS.get(sub) or self._syn.get(sub)
                if res:
                    cat = self._resolve_to_catalog(res)
                    if cat:
                        return cat
                sub_s = _normalize_plural(sub)
                if sub_s != sub:
                    res = ALL_SYNONYMS.get(sub_s) or self._syn.get(sub_s)
                    if res:
                        cat = self._resolve_to_catalog(res)
                        if cat:
                            return cat

        # Fuzzy entity token match against category names
        for ent in entities:
            for tok in ent.lower().split():
                if len(tok) < 3 or tok in STOP_ENTITIES:
                    continue
                m = process.extractOne(tok, self._cat_names, scorer=fuzz.ratio, score_cutoff=82)
                if m:
                    logger.info(f"🔍 Fuzzy entity '{tok}' → '{m[0]}'")
                    return m[0]

        # Fuzzy query word match
        words = [w for w in q_lower.split() if len(w) > 3 and w not in STOP_ENTITIES]
        for w in words:
            m = process.extractOne(w, self._cat_names, scorer=fuzz.ratio, score_cutoff=85)
            if m:
                logger.info(f"🔍 Fuzzy query word '{w}' → '{m[0]}'")
                return m[0]

        return None

    def _resolve_to_catalog(self, canonical: str) -> Optional[str]:
        c = canonical.lower()
        if c in self._categories:
            return c
        m = process.extractOne(c, self._cat_names, scorer=fuzz.partial_ratio, score_cutoff=75)
        return m[0] if m else None

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────

    def _clean_entities(self, entities: List[str]) -> List[str]:
        cleaned = []
        for ent in entities:
            if re.match(r"^\d+(?:\.\d+)?$", ent):
                continue
            tokens = ent.lower().split()
            meaningful = [
                t for t in tokens
                if t not in STOP_ENTITIES
                and not re.match(r"^\d+(?:\.\d+)?$", t)
            ]
            if not meaningful:
                continue
            result = " ".join(meaningful)
            if len(result) > 1:
                cleaned.append(result)
        return cleaned

    def _extract_brand(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for brand, kws in BRAND_PATTERNS.items():
            for kw in kws:
                if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                    return brand
        return None

    def _extract_negations(self, text: str) -> List[str]:
        negated = []
        for pat in [
            r"\bnot\s+(?:a\s+|an\s+|the\s+)?([a-z]+(?:\s+[a-z]+){0,2})\b",
            r"\bwithout\s+([a-z]+(?:\s+[a-z]+){0,2})\b",
        ]:
            for m in re.finditer(pat, text.lower()):
                term = m.group(1).strip()
                if len(term) > 2:
                    negated.append(term)
        return list(set(negated))

    def _explicit_sort(self, query: str) -> Optional[tuple]:
        q = query.lower()
        for phrase, (stype, sdir) in SORT_OVERRIDES.items():
            if phrase in q:
                logger.info(f"📊 Explicit sort: '{phrase}' → {stype}/{sdir}")
                return f"{stype}_sort", sdir
        return None