import os
os.environ["TQDM_DISABLE"] = "1"
from tqdm import tqdm
tqdm.disable = True
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import logging
import torch
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer, CrossEncoder, util
from rapidfuzz import fuzz, process

from text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)


class SearchEngine:
    def __init__(self, products: List[Dict[str, Any]],
                 bi_encoder_name: str = "all-MiniLM-L6-v2",
                 cross_encoder_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.products = products
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.normalizer = TextNormalizer()

        self.bi_encoder = SentenceTransformer(bi_encoder_name, device=self.device)
        self.cross_encoder = CrossEncoder(cross_encoder_name, device=self.device)

        self._build_product_indices()

        logger.info(f"🔧 Encoding {len(self.products)} products...")
        self.product_embeddings = self.bi_encoder.encode(
            self.product_texts,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        logger.info(f"✅ SearchEngine ready")

    def _build_product_indices(self):
        self.product_by_id = {}
        self.product_by_name = {}
        self.product_by_category = {}
        self.product_by_brand = {}
        self.product_texts = []          # used for encoding (with normalization)
        self.original_names = []          # for fuzzy matching
        self.category_price_ranges = {}

        for p in self.products:
            # Ensure price is float and in dollars
            price = p.get("price", 0)
            if isinstance(price, str):
                price = float(price.replace(',', ''))
            if price > 1000 and price < 1000000:  # cents -> dollars
                price = round(price / 100.0, 2)
            p["price"] = float(price)

            pid = p.get("id")
            if pid:
                self.product_by_id[pid] = p

            name = p.get("name", "").lower().strip()
            if name:
                self.product_by_name[name] = p
                self.original_names.append(name)

            cat = p.get("category", "").lower().strip()
            if cat:
                if cat not in self.product_by_category:
                    self.product_by_category[cat] = []
                self.product_by_category[cat].append(p)

                # Track price range
                price_val = p.get("price", 0)
                if cat not in self.category_price_ranges:
                    self.category_price_ranges[cat] = {"min": price_val, "max": price_val}
                else:
                    self.category_price_ranges[cat]["min"] = min(self.category_price_ranges[cat]["min"], price_val)
                    self.category_price_ranges[cat]["max"] = max(self.category_price_ranges[cat]["max"], price_val)

            brand = p.get("brand", "").lower().strip()
            if brand:
                if brand not in self.product_by_brand:
                    self.product_by_brand[brand] = []
                self.product_by_brand[brand].append(p)

            # Build rich text for embedding: include normalized version
            text = self._build_product_text(p)
            self.product_texts.append(text)

        logger.info(f"📂 Available categories: {sorted(self.product_by_category.keys())}")
        logger.info(f"📂 Sample products per category: { {k: len(v) for k, v in list(self.product_by_category.items())[:5]} }")

    def _build_product_text(self, product: Dict[str, Any]) -> str:
        """Combine product fields and also add a normalized version."""
        raw_name = product.get("name", "")
        raw_category = product.get("category", "")
        raw_brand = product.get("brand", "")
        raw_desc = product.get("description", "")
        raw_parts = [raw_name, raw_category, raw_brand, raw_desc]

        # Normalize a copy for better semantic matching
        norm_parts = [self.normalizer.normalize(part, for_semantic=True) for part in raw_parts if part]
        # Keep both raw and normalized to catch variations
        combined = " ".join(raw_parts) + " " + " ".join(norm_parts)
        return combined.lower()

    def _fuzzy_match_product(self, query: str, threshold: int = 60) -> Optional[Dict]:
        """Fuzzy match query against product names (using normalized query)."""
        if not query:
            return None
        # Normalize query for matching as well
        norm_query = self.normalizer.normalize(query, for_semantic=True)
        if norm_query in self.product_by_name:
            return self.product_by_name[norm_query]
        match = process.extractOne(
            norm_query,
            self.original_names,           # match against original names (they are lowercased)
            scorer=fuzz.partial_token_sort_ratio,
            score_cutoff=threshold
        )
        if match:
            matched_name, score, _ = match
            logger.info(f"🎯 Fuzzy match: '{query}' -> '{matched_name}' ({score})")
            return self.product_by_name[matched_name]
        return None

    def _get_category_products(self, category: str) -> List[Dict]:
        if not category:
            return []
        cat_lower = category.lower().strip()
        logger.info(f"🔎 Looking for category '{cat_lower}' in product_by_category keys: {list(self.product_by_category.keys())}")
        if cat_lower in self.product_by_category:
            logger.info(f"✅ Exact category match: {len(self.product_by_category[cat_lower])} products")
            return self.product_by_category[cat_lower]
        # Partial match
        for cat_name, products in self.product_by_category.items():
            if cat_lower in cat_name or cat_name in cat_lower:
                logger.info(f"🔍 Partial category match: '{cat_lower}' -> '{cat_name}' ({len(products)} products)")
                return products
        # Fallback scan across all products (category field)
        matched = []
        for p in self.products:
            p_cat = p.get("category", "").lower().strip()
            if cat_lower in p_cat or p_cat in cat_lower:
                matched.append(p)
        if matched:
            logger.info(f"🔍 Fallback category scan found {len(matched)} products")
            return matched
        # Still nothing – try scanning product names
        name_matched = []
        for p in self.products:
            p_name = p.get("name", "").lower()
            if cat_lower in p_name:
                name_matched.append(p)
        if name_matched:
            logger.info(f"🔍 Name-based fallback found {len(name_matched)} products for category '{category}'")
            return name_matched
        logger.warning(f"⚠️ No products found for category '{category}'")
        return []

    def _apply_constraints(self, products: List[Dict], constraints: Dict[str, Any]) -> List[Dict]:
        if not constraints:
            logger.info("📊 No constraints to apply")
            return products
        filtered = products.copy()
        orig_count = len(filtered)

        logger.info(f"📊 Applying constraints: {constraints} on {orig_count} products")

        if "price_min" in constraints:
            min_price = float(constraints["price_min"])
            before = len(filtered)
            filtered = [p for p in filtered if p.get("price", 0) >= min_price - 1e-9]
            logger.info(f"📊 Price >= ${min_price:.2f}: {len(filtered)}/{before}")
        if "price_max" in constraints:
            max_price = float(constraints["price_max"])
            before = len(filtered)
            filtered = [p for p in filtered if p.get("price", 0) <= max_price + 1e-9]
            logger.info(f"📊 Price <= ${max_price:.2f}: {len(filtered)}/{before}")

        if "rating_min" in constraints:
            min_rating = float(constraints["rating_min"])
            before = len(filtered)
            # Products with rating None are considered as 0 (won't pass positive min)
            filtered = [p for p in filtered if p.get("rating", 0) is not None and p.get("rating", 0) >= min_rating - 1e-9]
            logger.info(f"📊 Rating >= {min_rating}: {len(filtered)}/{before}")
        if "rating_max" in constraints:
            max_rating = float(constraints["rating_max"])
            before = len(filtered)
            filtered = [p for p in filtered if p.get("rating", 5) is not None and p.get("rating", 5) <= max_rating + 1e-9]
            logger.info(f"📊 Rating <= {max_rating}: {len(filtered)}/{before}")

        logger.info(f"📊 After constraints: {len(filtered)}/{orig_count}")
        return filtered

    def _apply_subcategory_filter(self, products: List[Dict], subcategory_keywords: List[str]) -> List[Dict]:
        if not subcategory_keywords:
            return products
        filtered = []
        for p in products:
            text = self._build_product_text(p)
            if any(kw in text for kw in subcategory_keywords):
                filtered.append(p)
        logger.info(f"🎮 Subcategory filter ({subcategory_keywords}): {len(filtered)}/{len(products)}")
        return filtered

    def _apply_sorting(self, products: List[Dict], constraints: Dict[str, Any]) -> List[Dict]:
        if not products:
            return products
        sorted_products = products.copy()
        if "price_sort" in constraints:
            if constraints["price_sort"] == "asc":
                sorted_products.sort(key=lambda x: x.get("price", float('inf')))
                logger.info("📊 Sorted by price: low to high")
            else:
                sorted_products.sort(key=lambda x: x.get("price", 0), reverse=True)
                logger.info("📊 Sorted by price: high to low")
        elif "rating_sort" in constraints:
            if constraints["rating_sort"] == "desc":
                sorted_products.sort(key=lambda x: x.get("rating", 0) or -1, reverse=True)
                logger.info("📊 Sorted by rating: high to low")
            else:  # asc
                sorted_products.sort(key=lambda x: x.get("rating", 0) or 0)
                logger.info("📊 Sorted by rating: low to high")
        else:
            # Default relevance
            if any(p.get("relevance_score") for p in sorted_products):
                sorted_products.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return sorted_products

    def search(
        self,
        query: str,
        product_entities: List[str] = None,
        brand: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        search_category: Optional[str] = None,
        subcategory_keywords: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:

        logger.info(f"🔍 Search started: query='{query}', category='{search_category}', subcategory_keywords={subcategory_keywords}, constraints={constraints}")

        # ------------------------------------------------------------
        # 1. Exact product match – but do NOT return immediately.
        #    We'll collect it as a high‑relevance candidate and continue.
        # ------------------------------------------------------------
        exact_match = self._fuzzy_match_product(query)
        exact_candidates = []
        if exact_match:
            logger.info(f"✅ Fuzzy match found: {exact_match.get('name')}")
            exact_match["relevance_score"] = 1.0
            exact_candidates = [exact_match]

        # ------------------------------------------------------------
        # 2. Get initial candidates based on category (if provided)
        # ------------------------------------------------------------
        if search_category:
            candidates = self._get_category_products(search_category)
            logger.info(f"📂 Category '{search_category}': {len(candidates)} initial candidates")
            if not candidates:
                logger.info("⚠️ No products in specified category, falling back to all products.")
                candidates = self.products.copy()
        else:
            candidates = self.products.copy()
            logger.info(f"📂 No category specified, using all products: {len(candidates)}")

        # ------------------------------------------------------------
        # 3. Add exact match product(s) to candidates (deduplicate later)
        # ------------------------------------------------------------
        if exact_candidates:
            # Add them, but we'll deduplicate after merging
            candidates.extend(exact_candidates)

        # ------------------------------------------------------------
        # 4. Filter by brand
        # ------------------------------------------------------------
        if brand:
            brand_lower = brand.lower()
            brand_filtered = []
            for p in candidates:
                p_brand = p.get("brand", "").lower()
                p_name = p.get("name", "").lower()
                if brand_lower in p_brand or brand_lower in p_name:
                    brand_filtered.append(p)
            if brand_filtered:
                candidates = brand_filtered
                logger.info(f"🏷️ After brand '{brand}': {len(candidates)} products")
            else:
                logger.info(f"🏷️ No products for brand '{brand}', continuing without brand filter")

        # ------------------------------------------------------------
        # 5. Apply subcategory filter
        # ------------------------------------------------------------
        if subcategory_keywords:
            candidates = self._apply_subcategory_filter(candidates, subcategory_keywords)
            if not candidates:
                logger.info("⚠️ No products after subcategory filter")
                return []

        # ------------------------------------------------------------
        # 6. Apply price and rating constraints
        # ------------------------------------------------------------
        if constraints:
            candidates = self._apply_constraints(candidates, constraints)
            if not candidates:
                logger.info("⚠️ No products match constraints")
                return []

        # ------------------------------------------------------------
        # 7. Semantic ranking (only if we have multiple candidates)
        # ------------------------------------------------------------
        if len(candidates) > 1:
            candidate_texts = [self._build_product_text(p) for p in candidates]
            logger.info(f"🔎 Semantic ranking on {len(candidates)} candidates")

            # Bi-encoder similarity
            query_emb = self.bi_encoder.encode(query, convert_to_tensor=True)
            candidate_embs = self.bi_encoder.encode(candidate_texts, convert_to_tensor=True)
            similarities = util.cos_sim(query_emb, candidate_embs)[0]
            for i, p in enumerate(candidates):
                p["relevance_score"] = float(similarities[i])

            # Sort and take top 50 for cross-encoder
            candidates.sort(key=lambda x: x["relevance_score"], reverse=True)
            candidates = candidates[:min(50, len(candidates))]

            if len(candidates) > 5:
                pairs = [(query, self._build_product_text(p)) for p in candidates]
                scores = self.cross_encoder.predict(pairs, show_progress_bar=False)
                for p, score in zip(candidates, scores):
                    p["relevance_score"] = float(score)
                candidates.sort(key=lambda x: x["relevance_score"], reverse=True)
        else:
            # Only one candidate – give it a high score if not already set
            if candidates and "relevance_score" not in candidates[0]:
                candidates[0]["relevance_score"] = 1.0

        # ------------------------------------------------------------
        # 8. Apply sorting (overrides relevance if requested)
        # ------------------------------------------------------------
        candidates = self._apply_sorting(candidates, constraints or {})

        # ------------------------------------------------------------
        # 9. Deduplicate (by name + price)
        # ------------------------------------------------------------
        seen = set()
        results = []
        for p in candidates:
            key = (p.get("name", ""), p.get("price", 0))
            if key not in seen:
                seen.add(key)
                results.append(p)

        logger.info(f"✅ Final {len(results)} results")
        # Log first few product names for verification
        for i, p in enumerate(results[:3]):
            logger.info(f"   Result {i+1}: {p.get('name')} (${p.get('price')}, rating {p.get('rating')})")
        return results[:top_k]