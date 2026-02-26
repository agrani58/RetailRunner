"""
recommendation_model.py — v8
Hybrid regex+ML constraint extractor.

Key fixes vs v7:
  - "rating below X"  → rating_MAX  (was incorrectly mapped to rating_min)
  - "rating above X"  → rating_MIN
  - Cleaner price-sort logic: under → asc, above → desc
  - ML regression used ONLY as fallback when regex finds nothing
"""

import os
import re
import json
import logging
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 1. Pure-regex constraint extractor
# ─────────────────────────────────────────────────────────────

_NUM = r"(\d+(?:[.,]\d+)?)"   # captures a number, possibly with comma/period

# Words that mean "price < X"
_PRICE_UNDER = (
    r"(?:under|below|beneath|less\s+than|cheaper\s+than|no\s+more\s+than"
    r"|not\s+over|not\s+exceeding|at\s+most|max(?:imum)?|up\s+to|within"
    r"|sub[-\s]?|staying\s+under|not\s+crossing|not\s+beyond|capped?\s+at)"
)
# Words that mean "price > X"
_PRICE_OVER = (
    r"(?:over|above|more\s+than|starting\s+(?:at|from)|at\s+least"
    r"|minimum|min(?:imum)?|from|higher\s+than|not\s+under"
    r"|nothing\s+under|not\s+(?:less|cheaper)|floor\s+(?:of\s+)?)"
)
_MONEY = r"\$?\s*" + _NUM + r"\s*(?:dollars?|bucks?|usd)?"


def _parse_number(s: str) -> float:
    return float(s.replace(",", ""))


def extract_constraints(query: str) -> dict:
    """
    Returns:
        price_min, price_max   : float | None
        rating_min, rating_max : float | None
        price_op               : 'less_than' | 'greater_than' | 'between' | 'none'
    """
    q = query.lower()
    result = dict(price_min=None, price_max=None,
                  rating_min=None, rating_max=None,
                  price_op="none")

    # ── PRICE ──────────────────────────────────────────────

    # between / range
    m = re.search(
        r"(?:between\s+)?" + r"\$?(\d+(?:[.,]\d+)?)" +
        r"\s*(?:and|to|-)\s*" + r"\$?(\d+(?:[.,]\d+)?)",
        q
    )
    if not m:
        m = re.search(
            r"from\s+\$?(\d+(?:[.,]\d+)?)\s*(?:to|up\s+to)\s*\$?(\d+(?:[.,]\d+)?)", q
        )
    if m:
        v1, v2 = _parse_number(m.group(1)), _parse_number(m.group(2))
        result["price_min"] = min(v1, v2)
        result["price_max"] = max(v1, v2)
        result["price_op"] = "between"
    else:
        # under / below
        m = re.search(_PRICE_UNDER + r"\s*" + _MONEY, q)
        if m:
            result["price_max"] = _parse_number(m.group(1))
            result["price_op"] = "less_than"
        else:
            # above / over
            m = re.search(_PRICE_OVER + r"\s*" + _MONEY, q)
            if m:
                v = _parse_number(m.group(1))
                # guard: if value ≤ 5 it's likely a rating, not a price
                if v > 5:
                    result["price_min"] = v
                    result["price_op"] = "greater_than"
            else:
                # budget / spend / limit / max patterns
                for pat in [
                    r"(?:budget|limit|spend)\s*(?:of|is|at|around)?\s*\$?(\d+(?:[.,]\d+)?)",
                    r"(?:spend|spending)\s+(?:up\s+to|no\s+more\s+than|around)?\s*\$?(\d+(?:[.,]\d+)?)",
                    r"\$?(\d+(?:[.,]\d+)?)\s*(?:is\s+(?:my\s+)?(?:absolute\s+)?(?:limit|ceiling|cap|max|budget))",
                    r"(?:around|about|roughly|approximately)\s+\$?(\d+(?:[.,]\d+)?)",
                    r"(?:max(?:imum)?\s+(?:of\s+)?\$?(\d+(?:[.,]\d+)?)|\$?(\d+(?:[.,]\d+)?)\s+(?:max(?:imum)?|or\s+less|tops?))",
                ]:
                    m = re.search(pat, q)
                    if m:
                        raw = next((g for g in m.groups() if g is not None), None)
                        if raw:
                            result["price_max"] = _parse_number(raw)
                            result["price_op"] = "less_than"
                        break

    # ── RATING ─────────────────────────────────────────────
    # IMPORTANT: "below/under X" → rating_MAX; "above/over X" → rating_MIN

    # between X and Y stars
    m = re.search(
        r"(?:rating|stars?|rated?|score)\s*(?:between|from)?\s*(\d+(?:\.\d+)?)"
        r"\s*(?:and|to|-)\s*(\d+(?:\.\d+)?)\s*(?:stars?)?", q
    )
    if not m:
        m = re.search(
            r"(?:between|from)\s+(\d+(?:\.\d+)?)\s*(?:and|to|-)\s*(\d+(?:\.\d+)?)"
            r"\s*(?:stars?(?:\s+rating)?|stars?|rated?)", q
        )
    if m:
        r1, r2 = float(m.group(1)), float(m.group(2))
        result["rating_min"] = min(r1, r2)
        result["rating_max"] = max(r1, r2)
    else:
        # "rating below / under X" → rating_max (upper bound)
        m = re.search(
            r"(?:rating|rated?|stars?|score)\s*"
            r"(?:below|under|less\s+than|not\s+(?:more|over)\s+than|at\s+most)\s*"
            r"(\d+(?:\.\d+)?)", q
        )
        if not m:
            m = re.search(
                r"(?:below|under|less\s+than|at\s+most)\s+"
                r"(\d+(?:\.\d+)?)\s*(?:star[s]?(?:\s+rating)?|stars?|in\s+(?:rating|reviews|score))",
                q
            )
        if m:
            v = float(m.group(1))
            if 0 < v <= 5:
                result["rating_max"] = v
        else:
            # "rating above / over / at least X" → rating_min (lower bound)
            m = re.search(
                r"(?:rating|rated?|stars?|score)\s*"
                r"(?:above|over|more\s+than|at\s+least|minimum|higher\s+than|not\s+(?:below|under)|no\s+(?:less|lower)\s+than)?\s*"
                r"(\d+(?:\.\d+)?)\s*(?:star[s]?(?:\s+rating)?|stars?)?",
                q
            )
            if not m:
                m = re.search(
                    r"(?:above|over|more\s+than|at\s+least|minimum|not\s+(?:below|under)|no\s+(?:less|lower)\s+than)\s+"
                    r"(\d+(?:\.\d+)?)\s*(?:star[s]?(?:\s+rating)?|stars?|in\s+(?:rating|reviews|score))?",
                    q
                )
            if not m:
                m = re.search(
                    r"(?:at\s+least|minimum|above|over)\s+(\d+(?:\.\d+)?)\s*(?:stars?|star\s+rating)", q
                )
            if m:
                v = float(m.group(1))
                if 0 < v <= 5:
                    result["rating_min"] = v

    return result


# ─────────────────────────────────────────────────────────────
# 2. ML Model (unchanged architecture)
# ─────────────────────────────────────────────────────────────

class SearchQueryModel(nn.Module):
    def __init__(self, model_name, n_op, n_cat, n_cur, n_st, n_sd):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        H = self.encoder.config.hidden_size

        def reg_head(hidden=256):
            return nn.Sequential(
                nn.Linear(H, hidden), nn.ReLU(), nn.Dropout(0.2),
                nn.Linear(hidden, 1), nn.Tanh()
            )

        self.price_value_1_head = reg_head()
        self.price_value_2_head = reg_head()
        self.rating_min_head    = reg_head()
        self.rating_max_head    = reg_head()
        self.price_op_head      = nn.Linear(H, n_op)
        self.filter_cat_head    = nn.Linear(H, n_cat)
        self.price_cur_head     = nn.Linear(H, n_cur)
        self.sort_type_head     = nn.Linear(H, n_st)
        self.sort_dir_head      = nn.Linear(H, n_sd)
        self.dropout            = nn.Dropout(0.3)

    def forward(self, input_ids, attention_mask):
        out    = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        pooled = self.dropout(out.last_hidden_state[:, 0, :])
        return {
            "price_value_1":   self.price_value_1_head(pooled).squeeze(-1),
            "price_value_2":   self.price_value_2_head(pooled).squeeze(-1),
            "rating_min":      self.rating_min_head(pooled).squeeze(-1),
            "rating_max":      self.rating_max_head(pooled).squeeze(-1),
            "price_operator":  self.price_op_head(pooled),
            "filter_category": self.filter_cat_head(pooled),
            "price_currency":  self.price_cur_head(pooled),
            "sort_type":       self.sort_type_head(pooled),
            "sort_dir":        self.sort_dir_head(pooled),
        }


# ─────────────────────────────────────────────────────────────
# 3. RecommendationModel wrapper
# ─────────────────────────────────────────────────────────────

class RecommendationModel:
    """
    Hybrid: regex (primary) + ML (fallback/sort signals).
    Regex always wins for numbers.  ML handles sort direction and filter_category.
    """

    RATING_KEYWORDS = {"rating", "ratings", "rated", "stars", "star", "score", "reviews"}

    def __init__(self, model_dir: str, device: str = "cpu"):
        self.device = device

        config_path  = os.path.join(model_dir, "config.json")
        encoder_path = os.path.join(model_dir, "encoder_mappings.json")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"config.json not found in {model_dir}")
        if not os.path.exists(encoder_path):
            raise FileNotFoundError(f"encoder_mappings.json not found in {model_dir}")

        with open(config_path)  as f: self.config  = json.load(f)
        with open(encoder_path) as f: self.encoders = json.load(f)

        self.max_price  = self.config.get("max_price",  3000.0)
        self.max_rating = self.config.get("max_rating", 5.0)

        self.op_classes  = self.encoders["price_operator"]
        self.cat_classes = self.encoders["filter_category"]
        self.cur_classes = self.encoders["price_currency"]
        self.st_classes  = self.encoders["sort_type"]
        self.sd_classes  = self.encoders["sort_direction"]

        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)

        model_name = self.config.get("model_name", "distilbert-base-uncased")
        self.model = SearchQueryModel(
            model_name,
            n_op  = len(self.op_classes),
            n_cat = len(self.cat_classes),
            n_cur = len(self.cur_classes),
            n_st  = len(self.st_classes),
            n_sd  = len(self.sd_classes),
        )
        weights_path = os.path.join(model_dir, "pytorch_model.bin")
        state_dict = torch.load(weights_path, map_location=device)
        self.model.load_state_dict(state_dict, strict=False)
        self.model.to(device)
        self.model.eval()
        logger.info(f"✅ RecommendationModel loaded from {model_dir}")

    def _cls(self, classes, idx):
        return classes[idx] if 0 <= idx < len(classes) else "none"

    def _decode_reg(self, v, scale):
        return None if v < 0 else round(float(v) * scale, 2)

    def _ml_inference(self, query: str) -> dict:
        enc = self.tokenizer(
            query, truncation=True, padding="max_length",
            max_length=128, return_tensors="pt"
        )
        iids = enc["input_ids"].to(self.device)
        mask = enc["attention_mask"].to(self.device)
        with torch.no_grad():
            out = self.model(iids, mask)

        op_idx   = int(out["price_operator"].argmax(1).item())
        cat_idx  = int(out["filter_category"].argmax(1).item())
        st_idx   = int(out["sort_type"].argmax(1).item())
        sd_idx   = int(out["sort_dir"].argmax(1).item())
        cat_conf = float(torch.softmax(out["filter_category"], 1).max().item())
        op_conf  = float(torch.softmax(out["price_operator"], 1).max().item())

        return {
            "ml_op":       self._cls(self.op_classes,  op_idx),
            "ml_op_conf":  op_conf,
            "ml_cat":      self._cls(self.cat_classes, cat_idx),
            "ml_cat_conf": cat_conf,
            "ml_sort_type":self._cls(self.st_classes,  st_idx),
            "ml_sort_dir": self._cls(self.sd_classes,  sd_idx),
            "ml_pv1": self._decode_reg(float(out["price_value_1"].item()), self.max_price),
            "ml_pv2": self._decode_reg(float(out["price_value_2"].item()), self.max_price),
            "ml_rv1": self._decode_reg(float(out["rating_min"].item()),    self.max_rating),
            "ml_rv2": self._decode_reg(float(out["rating_max"].item()),    self.max_rating),
        }

    def _has_rating_keyword(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self.RATING_KEYWORDS)

    def predict(self, query: str) -> dict:
        logger.info(f"🤖 Recommendation model input: '{query}'")

        regex = extract_constraints(query)
        ml    = self._ml_inference(query)

        # ── Determine final price bounds (regex wins) ──────────────
        price_min = regex["price_min"]
        price_max = regex["price_max"]
        price_op  = regex["price_op"]

        # ML fallback only if regex found nothing
        if price_min is None and price_max is None and price_op == "none":
            ml_op = ml["ml_op"]
            if ml_op != "none" and ml["ml_op_conf"] > 0.75:
                if ml_op == "less_than" and ml["ml_pv1"]:
                    price_max = ml["ml_pv1"]; price_op = "less_than"
                elif ml_op == "greater_than" and ml["ml_pv1"]:
                    price_min = ml["ml_pv1"]; price_op = "greater_than"
                elif ml_op == "between" and ml["ml_pv1"] and ml["ml_pv2"]:
                    price_min, price_max = ml["ml_pv1"], ml["ml_pv2"]; price_op = "between"

        # ── Rating bounds (regex wins, direction already correct) ───
        rating_min = regex["rating_min"]
        rating_max = regex["rating_max"]

        if self._has_rating_keyword(query) and rating_min is None and rating_max is None:
            if ml["ml_rv1"] and ml["ml_rv1"] > 0:
                rating_min = ml["ml_rv1"]
            if ml["ml_rv2"] and ml["ml_rv2"] > 0:
                rating_max = ml["ml_rv2"]

        if not self._has_rating_keyword(query):
            rating_min = rating_max = None

        # ── Sort logic ─────────────────────────────────────────────
        ml_sort_type = ml["ml_sort_type"]
        ml_sort_dir  = ml["ml_sort_dir"]

        # Decide sort keys for constraints dict
        constraints: dict = {}

        if price_min is not None:
            constraints["price_min"] = price_min
        if price_max is not None:
            constraints["price_max"] = price_max
        if rating_min is not None:
            constraints["rating_min"] = rating_min
        if rating_max is not None:
            constraints["rating_max"] = rating_max

        # Price sort: under→asc (show cheapest options), above→desc
        if price_op == "less_than":
            constraints["price_sort"] = "asc"
        elif price_op == "greater_than":
            constraints["price_sort"] = "desc"
        elif price_op == "between":
            # let ML decide if it's confident
            if ml_sort_type == "price":
                constraints["price_sort"] = ml_sort_dir if ml_sort_dir in ("asc", "desc") else "asc"
            else:
                constraints["price_sort"] = "asc"

        # Rating sort: if rating constraint present, sort by rating desc
        if rating_min is not None or rating_max is not None:
            if "price_sort" not in constraints:  # don't override price sort
                constraints["rating_sort"] = "desc"

        # ML sort override (only if no explicit sort yet)
        if "price_sort" not in constraints and "rating_sort" not in constraints:
            if ml_sort_type == "price" and ml_sort_dir in ("asc", "desc"):
                constraints["price_sort"] = ml_sort_dir
            elif ml_sort_type == "rating":
                constraints["rating_sort"] = "desc" if ml_sort_dir in ("desc", "none", "") else "asc"

        # filter_category from ML (used by QueryProcessor for sort-only queries)
        filter_cat = ml["ml_cat"]
        # Reconcile with what we actually found
        if (price_min is not None or price_max is not None) and (rating_min is not None or rating_max is not None):
            filter_cat = "combined"
        elif price_min is not None or price_max is not None:
            if filter_cat == "rating":
                filter_cat = "price"
        elif rating_min is not None or rating_max is not None:
            if filter_cat not in ("rating", "combined"):
                filter_cat = "rating"

        logger.info(f"   ➜ price_op: {price_op}, price_min: {price_min}, price_max: {price_max}")
        logger.info(f"   ➜ rating_min: {rating_min}, rating_max: {rating_max}")
        logger.info(f"   ➜ filter_cat: {filter_cat} (ML conf={ml['ml_cat_conf']:.2f})")
        logger.info(f"   ➜ final constraints: {constraints}")

        return {
            "constraints":     constraints,
            "filter_category": filter_cat,
            "sort_type":       ml_sort_type,
            "sort_dir":        ml_sort_dir,
            "price_operator":  price_op,
        }