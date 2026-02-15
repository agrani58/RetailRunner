import os
os.environ["TQDM_DISABLE"] = "1"
from tqdm import tqdm
tqdm.disable = True
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import logging
import re
import torch
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer, CrossEncoder, util
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class SearchEngine:
    def __init__(self, products: List[Dict[str, Any]], 
                 bi_encoder_name: str = "all-MiniLM-L6-v2",
                 cross_encoder_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.products = products
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Bi‑encoder for first‑stage retrieval
        self.bi_encoder = SentenceTransformer(bi_encoder_name, device=self.device)

        # Cross‑encoder for final re‑ranking
        self.cross_encoder = CrossEncoder(cross_encoder_name, device=self.device)

        # Cache for category matching
        self.category_match_cache = {}

        # Build category index and product lookup by category
        self._build_category_index()
        
        # Create category-based product groups for faster filtering
        self.products_by_category = {}
        self.products_by_type = {}
        
        for p in products:
            # Group by category
            cat = p.get("category", "").lower().strip()
            if cat:
                if cat not in self.products_by_category:
                    self.products_by_category[cat] = []
                self.products_by_category[cat].append(p)
            
            # Group by product type
            ptype = p.get("product_type", "").lower().strip()
            if ptype:
                if ptype not in self.products_by_type:
                    self.products_by_type[ptype] = []
                self.products_by_type[ptype].append(p)

        # Product texts and embeddings
        self.product_texts = []
        self.name_lookup = {}
        
        for p in products:
            text = self._build_product_text(p)
            self.product_texts.append(text)
            name = p.get("name", "").lower()
            if name:
                self.name_lookup[name] = p

        logger.info(f"🔧 Encoding {len(self.product_texts)} products with bi‑encoder...")
        self.product_embeddings = self.bi_encoder.encode(
            self.product_texts,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        logger.info(f"✅ SearchEngine ready, device: {self.device}")

    def _build_category_index(self):
        categories = set()
        for p in self.products:
            cat = p.get("category", "").strip()
            if cat:
                categories.add(cat.lower())
        self.category_names = list(categories)
        if self.category_names:
            self.category_embeddings = self.bi_encoder.encode(
                self.category_names,
                convert_to_tensor=True,
                show_progress_bar=False
            )
            logger.info(f"📚 Indexed {len(self.category_names)} unique categories")
        else:
            self.category_embeddings = None

    def _match_category(self, text: str, threshold: float = 0.7) -> Optional[str]:
        """Find the closest matching category for a text (entity or query)."""
        if not self.category_names:
            return None
            
        # Check cache first
        cached = self.category_match_cache.get(text)
        if cached:
            cat, score = cached
            return cat if score >= threshold else None

        # Try exact match first
        text_lower = text.lower()
        for cat in self.category_names:
            if text_lower == cat or text_lower in cat or cat in text_lower:
                self.category_match_cache[text] = (cat, 1.0)
                return cat

        # Try semantic match
        text_emb = self.bi_encoder.encode(
            text,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        scores = util.cos_sim(text_emb, self.category_embeddings)[0]
        best_score, best_idx = scores.max(dim=0)
        best_score = best_score.item()
        
        if best_score >= threshold:
            best_cat = self.category_names[best_idx.item()]
            self.category_match_cache[text] = (best_cat, best_score)
            return best_cat
            
        return None

    def _build_product_text(self, product: Dict[str, Any]) -> str:
        parts = [
            product.get("name", ""),
            product.get("category", ""),
            product.get("product_type", ""),
            product.get("description", ""),
            product.get("brand", ""),
        ]
        return " ".join([p for p in parts if p]).lower()

    def _product_matches_entities(self, product: Dict, entities: List[str]) -> bool:
        """Check if product matches any of the entity terms."""
        if not entities:
            return True
            
        name = product.get("name", "").lower()
        cat = product.get("category", "").lower()
        ptype = product.get("product_type", "").lower()
        description = product.get("description", "").lower()
        
        searchable_text = f"{name} {cat} {ptype} {description}"
        
        for entity in entities:
            entity_lower = entity.lower()
            # Direct match
            if entity_lower in searchable_text:
                return True
            # Word-by-word match for multi-word entities
            if len(entity_lower.split()) > 1:
                if all(word in searchable_text for word in entity_lower.split()):
                    return True
                    
        return False

    def _filter_candidates(self, products: List[Dict], entities: List[str], brand: Optional[str]) -> List[Dict]:
        """Filter products by entities and brand."""
        if not entities and not brand:
            return products

        filtered = []
        for p in products:
            # Entity check
            if entities and not self._product_matches_entities(p, entities):
                continue

            # Brand check
            if brand:
                brand_lower = brand.lower()
                name = p.get("name", "").lower()
                brand_field = p.get("brand", "").lower()
                if not (brand_lower in name or brand_lower == brand_field):
                    continue

            filtered.append(p)

        return filtered

    # ------------------------------------------------------------------
    # 🎯 IMPROVED CONSTRAINT APPLICATION
    # ------------------------------------------------------------------
    def _apply_constraints(self, products: List[Dict], constraints: Dict[str, Any]) -> List[Dict]:
        """
        Apply rating and price filters, then sort appropriately.
        """
        if not constraints:
            return products

        # Step 1: Rating filters
        rating_filtered = products
        if "rating_min" in constraints:
            min_rating = constraints["rating_min"]
            rating_filtered = [p for p in rating_filtered if p.get("rating") is not None and p["rating"] >= min_rating]
        if "rating_max" in constraints:
            max_rating = constraints["rating_max"]
            rating_filtered = [p for p in rating_filtered if p.get("rating") is not None and p["rating"] <= max_rating]

        if not rating_filtered:
            return []

        # Step 2: Price filters (applied to rating_filtered)
        price_filtered = rating_filtered
        if "price_min" in constraints:
            min_price = constraints["price_min"]
            price_filtered = [p for p in price_filtered if p.get("price", 0) >= min_price]
        if "price_max" in constraints:
            max_price = constraints["price_max"]
            price_filtered = [p for p in price_filtered if p.get("price", 0) <= max_price]

        # Decide which list to use: if price filters removed everything, fall back to rating_filtered
        if price_filtered:
            candidates = price_filtered
        else:
            logger.warning(f"⚠️ Price filters removed all {len(rating_filtered)} rating‑qualified products, using rating‑filtered only")
            candidates = rating_filtered

        # Step 3: Sorting
        if candidates:
            # Default rating sort descending if any rating constraint present and no explicit rating_sort
            if ("rating_min" in constraints or "rating_max" in constraints) and "rating_sort" not in constraints:
                candidates.sort(key=lambda x: x.get("rating") if x.get("rating") is not None else -1, reverse=True)
            elif "rating_sort" in constraints:
                if constraints["rating_sort"] == "desc":
                    candidates.sort(key=lambda x: x.get("rating") if x.get("rating") is not None else -1, reverse=True)
                elif constraints["rating_sort"] == "asc":
                    candidates.sort(key=lambda x: x.get("rating") if x.get("rating") is not None else float('inf'))

            # Price sorting (secondary)
            if "price_sort" in constraints:
                if constraints["price_sort"] == "asc":
                    candidates.sort(key=lambda x: x.get("price", float('inf')))
                elif constraints["price_sort"] == "desc":
                    candidates.sort(key=lambda x: x.get("price", 0), reverse=True)

        return candidates

    # ------------------------------------------------------------------
    # 🔍 MAIN SEARCH
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        product_entities: List[str] = None,
        brand: Optional[str] = None,
        exact_name: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        rerank_top_k: int = 50,
    ) -> List[Dict[str, Any]]:

        # 1. Exact match shortcut
        if exact_name:
            for p in self.products:
                if p.get("name", "").lower() == exact_name.lower():
                    p["relevance_score"] = 1.0
                    if constraints:
                        p_list = self._apply_constraints([p], constraints)
                        if p_list:
                            return p_list
                    return [p]

        # 2. Try to narrow down candidates using category matching based on entities
        candidates = self.products
        used_category = None
        
        if product_entities:
            for entity in product_entities:
                # Try to match to a category
                matched_cat = self._match_category(entity)
                if matched_cat and matched_cat in self.products_by_category:
                    candidates = self.products_by_category[matched_cat]
                    used_category = matched_cat
                    logger.info(f"📂 Filtered to category '{matched_cat}' based on entity '{entity}'")
                    break
                
                # Try to match to product type
                if entity in self.products_by_type:
                    candidates = self.products_by_type[entity]
                    logger.info(f"📂 Filtered to product type '{entity}'")
                    break
        
        # 3. Apply entity and brand filtering
        if product_entities or brand:
            filtered = self._filter_candidates(candidates, product_entities, brand)
            if filtered:
                candidates = filtered
            elif candidates != self.products:
                # If filtering removed everything but we had category filtering, fall back to category
                logger.warning(f"⚠️ Entity filtering removed all candidates, using category '{used_category}' unfiltered")
                # candidates already = category products
            else:
                # No category filter and no entities matched any product -> try to match the query to a category
                logger.info("⚠️ No candidates after filtering - trying to match query to a category")
                query_category = self._match_category(query)
                if query_category and query_category in self.products_by_category:
                    candidates = self.products_by_category[query_category]
                    used_category = query_category
                    logger.info(f"📂 Fallback to category '{query_category}' based on query")
                else:
                    # If still no candidates, use semantic fallback
                    logger.info("⚠️ No candidates after filtering - performing semantic fallback with corrected query")
                    query_emb = self.bi_encoder.encode(query, convert_to_tensor=True, show_progress_bar=False)
                    scores = util.cos_sim(query_emb, self.product_embeddings)[0]
                    top_indices = scores.topk(min(50, len(scores))).indices
                    candidates = [self.products[idx] for idx in top_indices]

        # 4. If we have too many candidates, use bi-encoder for initial ranking
        if len(candidates) > 200:
            candidate_texts = [self._build_product_text(p) for p in candidates]
            query_emb = self.bi_encoder.encode(query, convert_to_tensor=True, show_progress_bar=False)
            candidate_embs = self.bi_encoder.encode(candidate_texts, convert_to_tensor=True, show_progress_bar=False)
            similarities = util.cos_sim(query_emb, candidate_embs)[0]
            top_indices = similarities.topk(min(100, len(similarities))).indices
            candidates = [candidates[int(idx)] for idx in top_indices]

        # 5. Cross-encoder re-ranking (if we have candidates)
        if candidates:
            rerank_count = min(rerank_top_k, len(candidates))
            pairs = [(query, self._build_product_text(p)) for p in candidates[:rerank_count]]
            cross_scores = self.cross_encoder.predict(pairs, show_progress_bar=False)

            for prod, score in zip(candidates[:rerank_count], cross_scores):
                prod["relevance_score"] = round(float(score), 3)

            # Sort by cross-encoder score
            reranked = sorted(candidates[:rerank_count], key=lambda x: x["relevance_score"], reverse=True)
        else:
            logger.warning("⚠️ No candidates for re-ranking")
            return []

        # 6. Apply constraints (filtering and sorting)
        if constraints:
            reranked = self._apply_constraints(reranked, constraints)

        # 7. Deduplicate
        results = self._deduplicate(reranked)

        return results[:top_k] if results else []

    @staticmethod
    def _deduplicate(products: List[Dict]) -> List[Dict]:
        seen = set()
        unique = []
        for p in products:
            key = (p.get("name", ""), p.get("price", 0))
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique