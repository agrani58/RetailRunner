"""
search_engine.py - v2 (with improved matching and fallback)
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class SearchEngine:
    """
    Search engine for product catalog with:
      - category filtering
      - entity (product name) filtering with token‑overlap scoring
      - price/rating constraints
      - sorting (by price, rating, relevance)
      - fallback to category browse when entity filter returns nothing
    """

    def __init__(self, products: List[Dict[str, Any]]):
        self.products = products
        self._build_index()

    def _build_index(self):
        """Build lookup structures for fast category and name matching."""
        self.by_category: Dict[str, List[Dict]] = {}
        self.all_names: List[str] = []
        for p in self.products:
            cat = p.get("category", "").lower().strip()
            if cat:
                self.by_category.setdefault(cat, []).append(p)
            name = p.get("name", "").lower()
            if name:
                self.all_names.append(name)

    # ------------------------------------------------------------
    # Public search API
    # ------------------------------------------------------------

    def search(
        self,
        query: str,
        product_entities: List[str],
        brand: Optional[str] = None,
        constraints: Optional[Dict] = None,
        search_category: Optional[str] = None,
        subcategory_keywords: Optional[List[str]] = None,
        exclude_terms: Optional[List[str]] = None,
        skip_entity_filter: bool = False,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Main search entry point.
        Returns a ranked list of products.
        """
        constraints = constraints or {}
        subcategory_keywords = subcategory_keywords or []
        exclude_terms = exclude_terms or []

        # ---- Step 1: Filter by category ----
        candidates = self._filter_by_category(search_category)
        if not candidates:
            logger.info("No candidates after category filter")
            return []

        # ---- Step 2: Apply entity (product) filter ----
        if not skip_entity_filter and (product_entities or subcategory_keywords):
            filtered = self._entity_filter(candidates, product_entities, subcategory_keywords)
            if filtered:
                candidates = filtered
                logger.info(f"Entity filter kept {len(candidates)} products")
            else:
                # Fallback: keep category results (browse)
                logger.warning(
                    f"Entity filter returned 0 matches for {product_entities}. "
                    "Falling back to category browse."
                )
                # candidates remain unchanged (category list)

        # ---- Step 3: Apply brand filter (with fallback) ----
        if brand:
            brand_lower = brand.lower()
            brand_filtered = [
                p for p in candidates
                if brand_lower in p.get("brand", "").lower()
                or brand_lower in p.get("name", "").lower()
            ]
            if brand_filtered:
                candidates = brand_filtered
                logger.info(f"Brand filter kept {len(candidates)} products")
            else:
                logger.warning(
                    f"Brand filter removed all products (brand='{brand}'). "
                    "Ignoring brand filter."
                )
                # keep candidates unchanged

        # ---- Step 4: Apply constraints (price, rating) ----
        candidates = self._apply_constraints(candidates, constraints)

        # ---- Step 5: Remove excluded terms ----
        if exclude_terms:
            candidates = self._exclude_terms(candidates, exclude_terms)

        # ---- Step 6: Score and sort ----
        scored = self._score_products(candidates, query, product_entities)
        sorted_results = self._sort_products(scored, constraints)

        return sorted_results[:top_k]

    # ------------------------------------------------------------
    # Filtering steps
    # ------------------------------------------------------------

    def _filter_by_category(self, category: Optional[str]) -> List[Dict]:
        """Return products belonging to the given category, or all if category is None."""
        if not category:
            return self.products[:]
        cat_lower = category.lower()
        # Exact category match
        if cat_lower in self.by_category:
            return self.by_category[cat_lower][:]
        # Fuzzy category match (fallback)
        candidates = []
        for cat, prods in self.by_category.items():
            if fuzz.partial_ratio(cat_lower, cat) > 80:
                candidates.extend(prods)
        return candidates

    def _entity_filter(
        self,
        products: List[Dict],
        entities: List[str],
        keywords: List[str]
    ) -> List[Dict]:
        """
        Improved entity filter using token overlap scoring.
        Returns products that score >= 70 against any entity/keyword.
        Multi‑word entities require at least 80% token overlap; fuzzy only for single‑word.
        """
        if not entities and not keywords:
            return products

        def score_product(product: Dict, phrase: str) -> int:
            name = product.get("name", "").lower()
            desc = product.get("description", "").lower()
            ptype = product.get("product_type", "").lower()

            phrase_lower = phrase.lower().strip()
            phrase_tokens = set(phrase_lower.split())
            name_tokens = set(re.split(r"[\s\-_]", name))

            # 1. Exact substring match (highest confidence)
            if phrase_lower in name:
                return 100

            # 2. All tokens present (order doesn't matter)
            if phrase_tokens.issubset(name_tokens):
                return 95

            # 3. Multi-word phrase: require high token overlap, no fuzzy fallback
            if len(phrase_tokens) > 1:
                overlap = len(phrase_tokens & name_tokens)
                ratio = overlap / len(phrase_tokens)
                if ratio >= 0.8:
                    # weighted score in range 70‑86
                    return int(70 + 20 * ratio)
                return 0

            # 4. Single-word phrase: use fuzzy matching
            fuzzy = fuzz.partial_ratio(phrase_lower, name)
            if fuzzy >= 80:
                return fuzzy
            # Also check description / product_type
            if phrase_lower in desc or phrase_lower in ptype:
                return 70
            return 0

        scored = []
        for prod in products:
            max_score = 0
            for phrase in (entities + keywords):
                s = score_product(prod, phrase)
                if s > max_score:
                    max_score = s
            if max_score >= 70:
                scored.append((prod, max_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored]

    def _apply_constraints(
        self,
        products: List[Dict],
        constraints: Dict[str, Any]
    ) -> List[Dict]:
        """Filter products by price and rating constraints."""
        result = products[:]

        price_min = constraints.get("price_min")
        if price_min is not None:
            result = [p for p in result if p.get("price", 0) >= price_min]

        price_max = constraints.get("price_max")
        if price_max is not None:
            result = [p for p in result if p.get("price", 0) <= price_max]

        rating_min = constraints.get("rating_min")
        if rating_min is not None:
            result = [p for p in result if (p.get("rating") or 0) >= rating_min]

        rating_max = constraints.get("rating_max")
        if rating_max is not None:
            result = [p for p in result if (p.get("rating") or 0) <= rating_max]

        return result

    def _exclude_terms(
        self,
        products: List[Dict],
        exclude_terms: List[str]
    ) -> List[Dict]:
        """Remove products whose names contain any excluded term."""
        if not exclude_terms:
            return products
        result = []
        for p in products:
            name_lower = p.get("name", "").lower()
            if not any(term.lower() in name_lower for term in exclude_terms):
                result.append(p)
        return result

    # ------------------------------------------------------------
    # Scoring and sorting
    # ------------------------------------------------------------

    def _score_products(
        self,
        products: List[Dict],
        query: str,
        entities: List[str]
    ) -> List[Tuple[Dict, float]]:
        """
        Assign a relevance score (0‑100) to each product.
        Exact name matches get the highest score.
        """
        if not products:
            return []

        query_lower = query.lower()
        entity_text = " ".join(entities).lower() if entities else query_lower

        scored = []
        for p in products:
            name = p.get("name", "").lower()
            score = 0

            # Exact match on name
            if entity_text == name:
                score = 100
            # Substring match (entity inside name or name inside entity)
            elif entity_text in name or name in entity_text:
                score = 90
            else:
                # Token overlap
                name_tokens = set(re.split(r"[\s\-_]", name))
                entity_tokens = set(entity_text.split())
                overlap = len(name_tokens & entity_tokens)
                if overlap > 0:
                    score = 70 + (overlap * 10) / max(len(entity_tokens), 1)
                else:
                    # Fuzzy fallback
                    fuzzy = fuzz.token_sort_ratio(entity_text, name)
                    score = fuzzy * 0.7  # weight fuzzy lower

            # Boost if query appears in description/tags
            desc = p.get("description", "").lower()
            tags = " ".join(p.get("tags", [])).lower()
            if entity_text in desc or entity_text in tags:
                score += 5

            scored.append((p, min(score, 100)))

        return scored

    def _sort_products(
        self,
        scored_products: List[Tuple[Dict, float]],
        constraints: Dict[str, Any]
    ) -> List[Dict]:
        """
        Sort by:
          - explicit price/rating sort directives,
          - otherwise by relevance score.
        """
        if not scored_products:
            return []

        price_sort = constraints.get("price_sort")  # "asc" or "desc"
        rating_sort = constraints.get("rating_sort")  # "asc" or "desc"

        # If price sort requested, use that as primary
        if price_sort:
            reverse = (price_sort == "desc")
            scored_products.sort(
                key=lambda x: x[0].get("price", 0),
                reverse=reverse
            )
        # If rating sort requested, use that
        elif rating_sort:
            reverse = (rating_sort == "desc")
            scored_products.sort(
                key=lambda x: x[0].get("rating", 0) or 0,
                reverse=reverse
            )
        # Default: sort by relevance score
        else:
            scored_products.sort(key=lambda x: x[1], reverse=True)

        return [p for p, _ in scored_products]


# ------------------------------------------------------------
# Standalone utility functions (for main.py / other modules)
# ------------------------------------------------------------

def get_spell_suggestion_response(
    spell_suggestion: Optional[str],
    result_count: int,
) -> Optional[str]:
    """Generate a response prefix for spell‑corrected queries."""
    if not spell_suggestion:
        return None
    if result_count == 0:
        return f"I couldn't find exact results. {spell_suggestion}. Still no matches found."
    return spell_suggestion


def get_not_found_response(
    original_query: str,
    entities: List[str],
    product_names: List[str],
    threshold: int = 72,
) -> Optional[str]:
    """
    When search returns 0 results, suggest a similar product name.
    """
    if not entities:
        return None
    entity = " ".join(entities)
    best = process.extractOne(
        entity,
        product_names,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold,
    )
    if best:
        return f"Did you mean '{best[0].title()}'?"
    return None