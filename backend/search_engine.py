import os
os.environ["TQDM_DISABLE"] = "1"
from tqdm import tqdm          # ← MUST import before using it
tqdm.disable = True           # now this works globally
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import logging
import re
import torch
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class SearchEngine:
    def __init__(self, products: List[Dict[str, Any]], model_name: str = "all-MiniLM-L6-v2"):
        self.products = products
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=self.device)

        # Cache for category matching
        self.category_match_cache = {}

        # ------------------------------------------------------------------
        # 🚀 DYNAMIC CATEGORY INDEX – built from actual product categories
        # ------------------------------------------------------------------
        self._build_category_index()

        # Product texts and embeddings
        self.product_texts = []
        self.name_lookup = {}
        for p in products:
            text = self._build_product_text(p)
            self.product_texts.append(text)
            name = p.get("name", "").lower()
            if name:
                self.name_lookup[name] = p

        logger.info(f"🔧 Encoding {len(self.product_texts)} products...")
        self.product_embeddings = self.model.encode(
            self.product_texts,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        logger.info(f"✅ SearchEngine ready, device: {self.device}")

    # ------------------------------------------------------------------
    # 🏗️ Build category index from product data
    # ------------------------------------------------------------------
    def _build_category_index(self):
        """Extract all unique category names, compute embeddings."""
        categories = set()
        for p in self.products:
            cat = p.get("category", "").strip()
            if cat:
                categories.add(cat.lower())
        self.category_names = list(categories)
        if self.category_names:
            self.category_embeddings = self.model.encode(
                self.category_names,
                convert_to_tensor=True,
                show_progress_bar=False
            )
            logger.info(f"📚 Indexed {len(self.category_names)} unique categories")
        else:
            self.category_embeddings = None

    # ------------------------------------------------------------------
    # 🔎 Find the closest category to a query entity (semantic) – WITH CACHE
    # ------------------------------------------------------------------
    def _match_category(self, entity: str, threshold: float = 0.75) -> Optional[str]:
        """Return the most similar category name if above threshold, else None."""
        if not self.category_names:
            return None

        # Check cache first
        cached = self.category_match_cache.get(entity)
        if cached:
            cat, score = cached
            return cat if score >= threshold else None

        entity_emb = self.model.encode(
            entity,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        scores = util.cos_sim(entity_emb, self.category_embeddings)[0]
        best_score, best_idx = scores.max(dim=0)
        best_score = best_score.item()
        best_cat = self.category_names[best_idx.item()] if best_score >= threshold else None

        # Store in cache
        self.category_match_cache[entity] = (best_cat, best_score)
        return best_cat

    # ------------------------------------------------------------------
    # 📦 Build searchable product text
    # ------------------------------------------------------------------
    def _build_product_text(self, product: Dict[str, Any]) -> str:
        parts = [
            product.get("name", ""),
            product.get("category", ""),
            product.get("product_type", ""),
            product.get("description", ""),
            product.get("brand", ""),
        ]
        return " ".join([p for p in parts if p]).lower()

    # ------------------------------------------------------------------
    # 🧹 Normalise string for exact matching
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_for_match(text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ------------------------------------------------------------------
    # ✅ ENTITY MATCHER – STRICT for multi‑word, FLEXIBLE for single‑word
    # ------------------------------------------------------------------
    def _product_contains_entity(self, product: Dict, entity: str) -> bool:
        name = product.get("name", "").lower()
        cat = product.get("category", "").lower()
        ptype = product.get("product_type", "").lower()

        norm_entity = self._normalize_for_match(entity)
        norm_name = self._normalize_for_match(name)
        norm_cat = self._normalize_for_match(cat)
        norm_ptype = self._normalize_for_match(ptype)

        # Multi‑word: must appear in name or product_type
        if len(entity.split()) >= 2:
            if entity in name or entity in ptype:
                return True
            if norm_entity in norm_name or norm_entity in norm_ptype:
                return True
            return False

        # Single‑word: flexible matching
        if entity in name or entity in cat or entity in ptype:
            return True
        if entity.endswith('s'):
            singular = entity[:-1]
            if singular in name or singular in cat or singular in ptype:
                return True
        if norm_entity in norm_name or norm_entity in norm_cat or norm_entity in norm_ptype:
            return True
        matched_category = self._match_category(entity)
        if matched_category and matched_category == cat:
            return True
        return False

    # ------------------------------------------------------------------
    # 🎯 Candidate filtering
    # ------------------------------------------------------------------
    def _filter_candidates(self, products: List[Dict], entities: List[str], brand: Optional[str]) -> List[Dict]:
        if not entities and not brand:
            return products

        filtered = []
        for p in products:
            entity_ok = True
            if entities:
                entity_ok = False
                for ent in entities:
                    if self._product_contains_entity(p, ent):
                        entity_ok = True
                        break

            brand_ok = True
            if brand:
                brand_lower = brand.lower()
                name = p.get("name", "").lower()
                brand_field = p.get("brand", "").lower()
                brand_ok = brand_lower in name or brand_lower == brand_field

            if entity_ok and brand_ok:
                filtered.append(p)

        return filtered

    # ------------------------------------------------------------------
    # 🔍 MAIN SEARCH
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        product_entities: List[str] = None,
        brand: Optional[str] = None,
        exact_name: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.25,
    ) -> List[Dict[str, Any]]:

        if exact_name:
            for p in self.products:
                if p.get("name", "").lower() == exact_name.lower():
                    p["relevance_score"] = 1.0
                    return [p]

        candidates = self._filter_candidates(self.products, product_entities, brand)

        if not candidates:
            logger.info("⚠️ No candidates – fuzzy fallback (filtered by entities)")
            return self._fuzzy_fallback_filtered(query, product_entities, top_k)

        query_emb = self.model.encode(query, convert_to_tensor=True, show_progress_bar=False)
        filtered_texts = [self._build_product_text(p) for p in candidates]
        filtered_embs = self.model.encode(filtered_texts, convert_to_tensor=True, show_progress_bar=False)

        similarities = util.cos_sim(query_emb, filtered_embs)[0]
        top_indices = similarities.topk(min(top_k * 2, len(similarities))).indices

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= threshold:
                product = candidates[int(idx)].copy()
                product["relevance_score"] = round(score, 3)
                results.append(product)

        results.sort(key=lambda x: x["relevance_score"], reverse=True)

        if product_entities:
            filtered_results = []
            for p in results:
                if any(self._product_contains_entity(p, ent) for ent in product_entities):
                    filtered_results.append(p)
            results = filtered_results

        results = self._deduplicate(results)
        if results:
            return results[:top_k]

        logger.info("⚠️ No semantic matches – fuzzy fallback (filtered)")
        return self._fuzzy_fallback_filtered(query, product_entities, top_k)

    # ------------------------------------------------------------------
    # 🎯 FUZZY FALLBACK – with entity filtering
    # ------------------------------------------------------------------
    def _fuzzy_fallback_filtered(self, query: str, entities: List[str], top_k: int) -> List[Dict]:
        query_lower = query.lower()
        scored = []
        for p in self.products:
            if entities and not any(self._product_contains_entity(p, ent) for ent in entities):
                continue

            name = p.get("name", "").lower()
            score = fuzz.partial_ratio(query_lower, name) / 100.0

            cat = p.get("category", "").lower()
            ptype = p.get("product_type", "").lower()
            boost = 0.0
            if any(word in cat for word in query_lower.split() if len(word) > 2):
                boost = 0.3
            if any(word in ptype for word in query_lower.split() if len(word) > 2):
                boost = max(boost, 0.3)

            final_score = score * 0.6 + boost
            if final_score > 0.3:
                p_copy = p.copy()
                p_copy["relevance_score"] = round(final_score, 3)
                scored.append((final_score, p_copy))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [p for _, p in scored]
        return self._deduplicate(results)[:top_k]

    # ------------------------------------------------------------------
    # 🧹 Deduplicate by (name, price)
    # ------------------------------------------------------------------
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