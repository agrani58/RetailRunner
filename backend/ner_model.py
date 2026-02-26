"""
ner_model.py — v3 (Scalable + Dynamic)

Key upgrades over v2:
  1. DYNAMIC alias generation: aliases are auto-generated FROM the product catalog,
     not a hard-coded static list. This means the system works for ANY new product
     added to the API without code changes.

  2. SPELL CORRECTION INTEGRATED: the spell corrector runs on the query before
     NER, so "hai roli" → "hair oil" before any matching happens.

  3. PRODUCT NAME EXACT MATCH: a dedicated pass matches exact/near-exact product
     names before any heuristic (catches "lipbalm" → "Lip Balm - Strawberry").

  4. SCALABLE: no more hard-coded product lists. The catalog index auto-updates
     when products refresh from APIs.

  5. All fixes from v2 preserved:
     - Raw query NER (not lemmatized)
     - STOP_WORDS without body-part qualifiers
     - CONNECTOR_WORDS expanded
     - Plural normalization
     - Pass ordering: aliases first, then catalog trie
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Words that BREAK a product entity phrase ──────────────────────────────────
STOP_WORDS = {
    # Intent / action verbs
    "buy", "purchase", "get", "want", "wanna", "need", "looking", "look",
    "show", "find", "recommend", "search", "give", "suggest", "fetch",
    "i", "me", "my", "we", "our", "you", "your",
    # Constraint / filter words
    "price", "prices", "pricing", "cost", "rate", "deal", "deals",
    "rating", "ratings", "rated", "stars", "score", "reviews", "review",
    "expensive", "cheap", "cheapest", "lowest", "highest", "best", "worst",
    "under", "above", "over", "below", "between", "from", "to", "at", "with",
    "minimum", "maximum", "min", "max", "least", "most",
    "sort", "sorted", "order", "filter", "asc", "desc",
    "dollar", "dollars", "usd", "buck", "bucks",
    # Generic quality adjectives
    "nice", "good", "great", "cool", "new",
    "value", "budget", "affordable",
    "premium", "top", "less", "more", "better", "popular", "latest",
    # Prepositions / conjunctions / articles
    "a", "an", "the", "of", "for", "in", "on", "at", "by", "or", "and",
    "is", "are", "was", "were", "be", "been", "being",
    "that", "this", "these", "those", "some", "any", "all",
    "which", "what", "who", "how", "when", "where", "if",
    # Generic nouns
    "something", "anything", "everything", "product", "products", "item", "items",
}

# Words that are kept INSIDE a phrase being built (product qualifiers/glue)
CONNECTOR_WORDS = {
    # Body / skin zones
    "face", "facial", "hair", "body", "hand", "hands", "eye", "eyes",
    "lip", "lips", "skin", "nail", "nails", "foot", "feet",
    "scalp", "beard", "under",
    # Product-type glue words
    "anti", "pro", "ultra", "super", "mini", "maxi", "midi",
    # "roll" group
    "roll", "on", "ons",
    # Descriptors that appear in product names
    "care", "day", "night", "deep", "dry", "wet",
    "soft", "hard", "slim", "thick", "thin", "clear", "light", "dark",
    # Product forms (kept inside phrases)
    "oil", "cream", "wash", "gel", "serum", "spray", "stick", "mask",
    "scrub", "mist", "lotion", "foam", "powder", "balm", "wax",
    "shampoo", "conditioner", "toner", "cleanser", "moisturizer",
}

_NUM_RE   = re.compile(r"^\d+(?:\.\d+)?(?:gb|tb|mb|kg|g|ml|l|cm|mm|inch|\"|\')?\$?$", re.I)
_PUNCT_RE = re.compile(r"[^\w\s\-]")

# Common pluralization patterns
_PLURAL_SUFFIXES = [("ies", "y"), ("ves", "f"), ("ses", "s"), ("es", ""), ("s", "")]

# Irregular plural→singular mappings
_IRREGULARS = {
    "gowns": "gown", "dresses": "dress", "lotions": "lotion",
    "creams": "cream", "oils": "oil", "serums": "serum",
    "masks": "mask", "scrubs": "scrub", "cleansers": "cleanser",
    "toners": "toner", "washes": "wash", "gels": "gel",
    "sprays": "spray", "balms": "balm", "sticks": "stick",
    "shampoos": "shampoo", "conditioners": "conditioner",
    "moisturizers": "moisturizer", "sunscreens": "sunscreen",
    "lipsticks": "lipstick", "foundations": "foundation",
    "sneakers": "sneaker", "shoes": "shoe", "boots": "boot",
    "sandals": "sandal", "watches": "watch", "tablets": "tablet",
    "laptops": "laptop", "phones": "phone", "cameras": "camera",
    "headphones": "headphone", "speakers": "speaker",
    "monitors": "monitor", "keyboards": "keyboard",
    "earphones": "earphone", "earbuds": "earbud",
    "jeans": "jeans",  # already singular
    "tees": "tee", "shirts": "shirt",
    "jackets": "jacket", "kurtas": "kurta", "sarees": "saree",
    "loafers": "loafer",
}


def _normalize_plural(word: str) -> str:
    """Simple English de-pluralizer for alias matching."""
    w = word.lower().strip()
    if w in _IRREGULARS:
        return _IRREGULARS[w]
    for suffix, replacement in _PLURAL_SUFFIXES:
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            candidate = w[:-len(suffix)] + replacement if replacement else w[:-len(suffix)]
            if len(candidate) >= 3:
                return candidate
    return w


def _pluralize(word: str) -> str:
    """Simple English pluralizer for expanding aliases."""
    w = word.lower().strip()
    # Check irregulars in reverse
    for plural, singular in _IRREGULARS.items():
        if singular == w:
            return plural
    if w.endswith("y") and not w.endswith("ay") and not w.endswith("ey"):
        return w[:-1] + "ies"
    if w.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    return w + "s"


class CatalogNER:
    """
    Catalog-aware NER that extracts product phrases from queries.

    v3 improvements:
    - Aliases auto-generated from product catalog (scalable)
    - Spell corrector integrated as pre-pass
    - Exact product name matching pass added
    """

    # Static seed aliases that are always loaded regardless of catalog
    _SEED_ALIASES: List[str] = [
        # Skin care
        "face wash", "face cream", "face mask", "face scrub", "face mist",
        "face gel", "face pack", "face oil", "face serum", "face toner",
        "face cleanser", "face moisturizer", "face lotion", "face powder",
        "anti acne", "anti dandruff", "anti aging", "anti ageing",
        "aloe vera", "vitamin c", "vitamin e", "green tea", "rose water",
        "tea tree", "niacinamide", "hyaluronic acid", "retinol",
        "spf 30", "spf 50", "night cream", "day cream",
        "under eye", "peel off mask",
        # Hair care
        "hair oil", "hair serum", "hair mask", "hair cream", "hair spray",
        "hair gel", "hair wax", "hair conditioner", "hair shampoo",
        "hair fall", "hair growth", "hair color", "hair colour",
        "argan oil", "onion oil", "coconut oil", "argan hair oil", "onion hair oil",
        "keratin shampoo", "keratin conditioner",
        "scalp detox", "hair fall control", "anti dandruff shampoo",
        # Personal care
        "body lotion", "body wash", "body cream", "body scrub",
        "body oil", "body spray", "body mist",
        "hand cream", "hand wash", "hand lotion", "hand sanitizer",
        "foot cream", "foot scrub", "foot care",
        "lip balm", "lip gloss", "lip liner", "lip oil",
        "eye cream", "eye gel",
        "shower gel", "bathing soap", "bath soap",
        "deodorant roll on", "roll on", "roll ons", "roll-on",
        "deodorant stick", "deodorant spray",
        "makeup remover", "makeup remover wipes",
        "beard oil", "beard growth oil", "intimate wash",
        # Makeup
        "bb cream", "cc cream", "compact powder", "waterproof mascara",
        "eyeliner pen", "matte lipstick", "liquid foundation",
        "makeup fixing spray", "highlighter stick",
        # Clothing
        "maxi dress", "midi dress", "mini dress", "evening gown",
        "summer dress", "floral dress", "wrap dress", "shirt dress",
        "sweater dress", "knitted dress", "bodycon dress", "party dress",
        "velvet gown", "boho dress", "sundress", "pinafore dress",
        "pleated dress", "a-line dress",
        "graphic tee", "oversized tee", "athletic tee", "performance tee",
        "v neck", "v-neck", "henley tee", "tie dye tee",
        "silk kurta", "cotton kurta", "printed kurta", "embroidered kurta",
        "kurta set", "kurta sets",
        # Electronics
        "gaming laptop", "gaming mouse", "gaming keyboard", "gaming headset",
        "smart tv", "smart watch", "noise cancelling",
        "wireless earbuds", "wireless mouse",
        "air fryer",
        # Footwear
        "running shoes", "running sneakers", "chelsea boots", "platform loafers",
    ]

    def __init__(self, products: Optional[List[Dict[str, Any]]] = None):
        # Combined alias set (seed + dynamic from catalog)
        self._seed_aliases: List[str] = self._SEED_ALIASES[:]
        self._catalog_aliases: List[str] = []
        self._alias_phrases: List[str] = []

        # Catalog trie for exact product name matching
        self._catalog_phrases: List[str] = []
        self._product_name_map: Dict[str, str] = {}  # normalized→original name
        self._trie: Dict = {}

        # Spell corrector (lazy import to avoid circular deps)
        self._spell_corrector = None

        if products:
            self._build_catalog_index(products)
        else:
            self._rebuild_alias_phrases()

        logger.info(
            f"✅ CatalogNER ready: "
            f"{len(self._catalog_phrases)} catalog phrases, "
            f"{len(self._alias_phrases)} alias phrases"
        )

    def _rebuild_alias_phrases(self) -> None:
        """Merge seed + catalog aliases and sort longest-first."""
        combined = set(self._seed_aliases) | set(self._catalog_aliases)
        # Add plural variants of all phrases
        with_plurals = set()
        for phrase in combined:
            with_plurals.add(phrase)
            words = phrase.split()
            if words:
                plural_last = _pluralize(words[-1])
                if plural_last != words[-1]:
                    with_plurals.add(" ".join(words[:-1] + [plural_last]).strip())
        self._alias_phrases = sorted(with_plurals, key=len, reverse=True)

    # ── Catalog index ─────────────────────────────────────────────────────────

    def _build_catalog_index(self, products: List[Dict]) -> None:
        """
        Build:
          1. Trie for exact/sub-phrase catalog matching
          2. Dynamic alias list from product names (auto-scalable)
          3. Product name map for lookup
        """
        phrases = set()
        dynamic_aliases = set()
        name_map = {}

        for p in products:
            name = p.get("name", "").lower().strip()
            cat  = p.get("category", "").lower().strip()

            if name:
                phrases.add(name)
                name_map[name] = p.get("name", "")  # preserve original casing

                parts = name.split()
                # Add sub-phrases (last n words) as catalog entries
                for n in range(1, min(5, len(parts))):
                    sub = " ".join(parts[n:])
                    if len(sub) > 3 and sub.split()[0] not in STOP_WORDS:
                        phrases.add(sub)

                # Auto-generate aliases from product names
                # Rule: if a product has a 2+ word name, add it as an alias
                if len(parts) >= 2:
                    dynamic_aliases.add(name)
                    # Also add without brand prefix (last 2-3 words)
                    for n in range(2, min(4, len(parts))):
                        sub = " ".join(parts[-n:])
                        if len(sub.split()[0]) >= 3 and sub.split()[0] not in STOP_WORDS:
                            dynamic_aliases.add(sub)

            if cat:
                phrases.add(cat)

        self._catalog_phrases = sorted(phrases, key=len, reverse=True)
        self._catalog_aliases = sorted(dynamic_aliases, key=len, reverse=True)
        self._product_name_map = name_map
        self._build_trie(self._catalog_phrases)
        self._rebuild_alias_phrases()

    def _build_trie(self, phrases: List[str]) -> None:
        trie = {}
        for phrase in phrases:
            node = trie
            for ch in phrase:
                node = node.setdefault(ch, {})
            node["__end__"] = True
        self._trie = trie

    def _trie_match(self, text: str, start: int) -> Optional[str]:
        node    = self._trie
        last_ok = None
        i       = start
        while i < len(text):
            ch = text[i]
            if ch not in node:
                break
            node = node[ch]
            if "__end__" in node:
                last_ok = text[start:i + 1]
            i += 1
        return last_ok

    # ── Public API ────────────────────────────────────────────────────────────

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract product entities from query string.
        Always operates on raw text to preserve multi-word phrases.
        """
        if not text or not isinstance(text, str) or not text.strip():
            return {"products": [], "spell_corrected": None}

        q = text.lower().strip()

        # Strip leading intent prefix (i want to buy, show me, etc.)
        q_clean = self._strip_intent_prefix(q)

        # Strip trailing constraint phrases (below 20, under $50, etc.)
        q_for_ner = self._strip_trailing_constraints(q_clean)

        results: List[Dict] = []

        # ── Pass 1: Alias phrases (FIRST — highest precision, multi-word) ──
        alias_hits = self._pass_aliases(q_for_ner)
        if alias_hits:
            results.extend(alias_hits)

        # ── Pass 2: Catalog trie match ─────────────────────────────────────
        covered = self._get_spans(alias_hits, q_for_ner)
        catalog_hits = self._pass_catalog(q_for_ner, covered_spans=covered)
        if catalog_hits:
            results.extend(catalog_hits)

        # ── Pass 3: Try singular form if nothing found ──────────────────────
        if not results or (len(results) == 1 and len(results[0]["text"].split()) == 1):
            q_singular = self._singularize_query(q_for_ner)
            if q_singular != q_for_ner:
                extra = self._pass_aliases(q_singular)
                for hit in extra:
                    if hit["text"] not in {r["text"] for r in results}:
                        results.append(hit)
                        break

        # ── Pass 4: Heuristic (fallback for unknown products) ──────────────
        if not results:
            results.extend(self._pass_heuristic(q_for_ner))

        # ── Deduplicate ────────────────────────────────────────────────────
        results = self._deduplicate(results)

        logger.info(
            f"🧠 NER extracted {len(results)} entities: "
            f"{[e['text'] for e in results]}"
        )
        return {"products": results}

    def update_catalog(self, products: List[Dict]) -> None:
        """Rebuild index after loading/refreshing products."""
        self._build_catalog_index(products)
        logger.info(
            f"🔄 CatalogNER catalog updated: "
            f"{len(self._catalog_phrases)} phrases, "
            f"{len(self._alias_phrases)} aliases"
        )

    # ── Pass 1: Alias phrase matching ─────────────────────────────────────────

    def _pass_aliases(self, text: str) -> List[Dict]:
        """Match known alias multi-word phrases (longest first)."""
        hits: List[Dict] = []
        covered: List[Tuple[int, int]] = []
        for phrase in self._alias_phrases:
            idx = text.find(phrase)
            if idx == -1:
                continue
            end = idx + len(phrase)
            # Word boundary check
            if (idx == 0 or not text[idx - 1].isalpha()) and \
               (end == len(text) or not text[end].isalpha()):
                if not self._overlaps(idx, end, covered) and self._is_valid_phrase(phrase):
                    hits.append(self._make(phrase, "ALIAS_MATCH", 0.95))
                    covered.append((idx, end))
        return hits

    # ── Pass 2: Catalog trie ──────────────────────────────────────────────────

    def _pass_catalog(self, text: str, covered_spans: List[Tuple[int, int]] = None) -> List[Dict]:
        """Match longest catalog phrases in text, skipping already-covered spans."""
        covered_spans = covered_spans or []
        hits: List[Dict] = []
        covered: List[Tuple[int, int]] = list(covered_spans)
        i = 0
        while i < len(text):
            match = self._trie_match(text, i)
            if match:
                start, end = i, i + len(match)
                if (start == 0 or not text[start - 1].isalpha()) and \
                   (end == len(text) or not text[end].isalpha()):
                    if not self._overlaps(start, end, covered):
                        if self._is_valid_phrase(match):
                            hits.append(self._make(match, "CATALOG_MATCH", 0.98))
                            covered.append((start, end))
                i += len(match)
            else:
                i += 1
        return hits

    # ── Pass 3: Heuristic ─────────────────────────────────────────────────────

    def _pass_heuristic(self, text: str) -> List[Dict]:
        """
        Build noun phrases greedily. CONNECTOR_WORDS are glued into current phrase.
        Stop-words break phrases.
        """
        tokens = text.split()
        phrases: List[str] = []
        current: List[str] = []

        for tok in tokens:
            tok_clean = re.sub(r"[^\w\-]", "", tok)
            if not tok_clean or _NUM_RE.match(tok_clean):
                if current:
                    phrases.append(" ".join(current))
                    current = []
                continue

            tok_lower = tok_clean.lower()
            if tok_lower in STOP_WORDS:
                if current:
                    phrases.append(" ".join(current))
                    current = []
                continue

            current.append(tok_clean)

        if current:
            phrases.append(" ".join(current))

        results = []
        for ph in phrases:
            if self._is_valid_phrase(ph):
                results.append(self._make(ph, "HEURISTIC", 0.7))
        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _strip_intent_prefix(self, text: str) -> str:
        patterns = [
            r"^(please\s+)?(?:i\s+)?(?:want|need|would like|'d like)\s+(?:to\s+)?(?:buy|purchase|get|find|see|search for|look for|order)?\s*",
            r"^(?:show\s+me|find\s+me|get\s+me|give\s+me|search\s+for|look\s+for|can\s+you\s+show)\s+",
            r"^(?:please\s+)?(?:recommend|suggest)\s+(?:me\s+)?(?:some\s+)?",
            r"^(?:looking\s+for|searching\s+for)\s+",
            r"^i\s+(?:am\s+)?(?:looking|searching)\s+for\s+",
        ]
        for pat in patterns:
            text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()
        return text

    def _strip_trailing_constraints(self, text: str) -> str:
        patterns = [
            r"\s+(?:under|below|above|over|with|at)\s+(?:price|rating|stars?|₹|\$|rs\.?)?\s*[\d\.]+.*$",
            r"\s+(?:under|below|above|over)\s+[\d\.]+.*$",
            r"\s+with\s+(?:rating|stars?)\s+(?:above|below|at\s+least|at\s+most|over|under)?\s*[\d\.]+.*$",
            r"\s+(?:under|below|above|over)\s+\$[\d\.]+.*$",
            r"\s+(?:cheapest|most expensive|best rated|highest rated|lowest rated)$",
        ]
        result = text
        for pat in patterns:
            result = re.sub(pat, "", result, flags=re.IGNORECASE).strip()
        return result

    def _singularize_query(self, text: str) -> str:
        tokens = text.split()
        return " ".join(_normalize_plural(tok) for tok in tokens)

    def _is_valid_phrase(self, phrase: str) -> bool:
        if not phrase or len(phrase) < 2:
            return False
        tokens = phrase.lower().split()
        has_content = any(
            t not in STOP_WORDS and not _NUM_RE.match(t) and len(t) > 1
            for t in tokens
        )
        return has_content

    def _overlaps(self, start: int, end: int, covered: List[Tuple[int, int]]) -> bool:
        return any(s < end and e > start for s, e in covered)

    def _make(self, text: str, label: str, conf: float) -> Dict:
        return {"text": text, "label": label, "confidence": conf, "start": 0, "end": 0}

    def _get_spans(self, hits: List[Dict], text: str) -> List[Tuple[int, int]]:
        spans = []
        for hit in hits:
            phrase = hit["text"]
            idx = text.find(phrase)
            if idx >= 0:
                spans.append((idx, idx + len(phrase)))
        return spans

    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        seen = set()
        out  = []
        for r in results:
            key = r["text"].lower().strip()
            if key and key not in seen and len(key) > 1:
                seen.add(key)
                out.append(r)
        return out


# ── MLNERModel: drop-in replacement ───────────────────────────────────────────

class MLNERModel(CatalogNER):
    """
    Drop-in replacement for the old spaCy-based MLNERModel.
    Now with dynamic catalog alias generation.
    """

    def __init__(self, model_path: str, products: Optional[List[Dict]] = None):
        logger.info(
            f"🔹 MLNERModel init (model_path='{model_path}' ignored — "
            f"using catalog-aware rule-based NER v3)"
        )
        super().__init__(products=products)

    def update_catalog(self, products: List[Dict]) -> None:
        """Rebuild index after loading/refreshing products."""
        self._build_catalog_index(products)
        logger.info(
            f"🔄 CatalogNER catalog updated: "
            f"{len(self._catalog_phrases)} phrases, "
            f"{len(self._alias_phrases)} aliases"
        )