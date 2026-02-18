import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class PriceExtractor:
    @staticmethod
    def extract(text: str) -> Dict[str, Any]:
        """Extract explicit price constraints using robust regex."""
        constraints = {}
        text_lower = text.lower()

        def extract_number(s):
            s = s.replace(',', '').strip()
            match = re.search(r'(\d+(?:\.\d+)?)', s)
            return float(match.group(1)) if match else None

        # --- Exact price ---
        exact_patterns = [
            r'(?:exactly|precisely|specifically)\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)(?:\s*dollars?)?',
            r'^([\d,]+(?:\.\d+)?)\s*dollars?$',
            r'^\$([\d,]+(?:\.\d+)?)$'
        ]
        for pattern in exact_patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = extract_number(match.group(1))
                if val is not None:
                    constraints['price_min'] = val
                    constraints['price_max'] = val
                    logger.info(f"💰 Exact price: ${val}")
                    return constraints

        # --- Range ---
        range_patterns = [
            r'(?:between|from)\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)\s*(?:and|to|-)\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)(?:\s*dollars?)?',
            r'(?:\$)?\s*([\d,]+(?:\.\d+)?)\s*(?:-|to)\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)(?:\s*dollars?)?'
        ]
        for pattern in range_patterns:
            match = re.search(pattern, text_lower)
            if match:
                min_val = extract_number(match.group(1))
                max_val = extract_number(match.group(2))
                if min_val is not None and max_val is not None and min_val <= max_val:
                    constraints['price_min'] = min_val
                    constraints['price_max'] = max_val
                    logger.info(f"💰 Price range: ${min_val}-${max_val}")
                    return constraints

        # --- Under / max ---
        under_patterns = [
            r'(?:under|less than|below|max|at most|up to)\s+(?:(?:price|cost)\s+)?(?:\$)?\s*([\d,]+(?:\.\d+)?)(?:\s*dollars?)?',
            r'price\s+(?:is\s+)?(?:under|less than|below|max)\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)',
            r'<=\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)',
            r'<\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)'
        ]
        for pattern in under_patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = extract_number(match.group(1))
                if val is not None:
                    constraints['price_max'] = val
                    logger.info(f"💰 Max price: ${val}")
                    return constraints

        # --- Over / min ---
        over_patterns = [
            r'(?:over|above|more than|min|at least|exceeding)\s+(?:(?:price|cost)\s+)?(?:\$)?\s*([\d,]+(?:\.\d+)?)(?:\s*dollars?)?',
            r'price\s+(?:is\s+)?(?:over|above|more than|min)\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)',
            r'>=\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)',
            r'>\s*(?:\$)?\s*([\d,]+(?:\.\d+)?)'
        ]
        for pattern in over_patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = extract_number(match.group(1))
                if val is not None:
                    constraints['price_min'] = val
                    logger.info(f"💰 Min price: ${val}")
                    return constraints

        return constraints


class RatingExtractor:
    @staticmethod
    def extract(text: str) -> Dict[str, Any]:
        """Extract explicit rating constraints."""
        constraints = {}
        text_lower = text.lower()

        def extract_rating(s):
            match = re.search(r'(\d+(?:\.\d+)?)', s)
            return float(match.group(1)) if match else None

        patterns = [
            (r'(?:above|over|more than|>)\s*(\d+(?:\.\d+)?)\s*(?:star|stars|rating)', 'min'),
            (r'(?:at least|minimum)\s*(\d+(?:\.\d+)?)\s*(?:star|stars|rating)', 'min'),
            (r'(?:below|under|less than|<)\s*(\d+(?:\.\d+)?)\s*(?:star|stars|rating)', 'max'),
            (r'(?:exactly|precisely)\s*(\d+(?:\.\d+)?)\s*(?:star|stars|rating)', 'exact'),
            (r'(\d+(?:\.\d+)?)\s*[+]\s*(?:star|stars|rating)', 'min'),
            (r'(\d+(?:\.\d+)?)-star', 'exact'),
        ]

        for pattern, typ in patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = extract_rating(match.group(1))
                if val is not None:
                    if typ == 'min':
                        constraints['rating_min'] = val
                        logger.info(f"⭐ Min rating: {val}")
                    elif typ == 'max':
                        constraints['rating_max'] = val
                        logger.info(f"⭐ Max rating: {val}")
                    elif typ == 'exact':
                        constraints['rating_min'] = val
                        constraints['rating_max'] = val
                        logger.info(f"⭐ Exact rating: {val}")
                    return constraints

        # Qualitative mappings
        qual_map = {
            '5 star': 4.9, 'five star': 4.9, 'perfect rating': 4.9,
            'excellent': 4.5, 'outstanding': 4.5, 'top rated': 4.5,
            'good': 4.0, 'great': 4.0, 'highly rated': 4.0,
            'decent': 3.5, 'average': 3.5,
        }
        for phrase, rating in qual_map.items():
            if phrase in text_lower:
                constraints['rating_min'] = rating
                logger.info(f"⭐ Qualitative rating from '{phrase}': {rating}")
                break

        return constraints


class HybridConstraintPredictor:
    """
    Predicts price/rating constraints using explicit extraction + qualitative fallbacks.
    Also detects sort intents (cheapest, most expensive, highest rated, lowest rated).
    """
    def __init__(self):
        self.price_extractor = PriceExtractor()
        self.rating_extractor = RatingExtractor()

        # Qualitative price thresholds (used only if no explicit numbers found)
        self.qualitative_price = {
            'budget': {'price_max': 100},
            'cheap': {'price_max': 100},
            'affordable': {'price_max': 100},
            'inexpensive': {'price_max': 100},
            'economical': {'price_max': 100},
            'value': {'price_max': 150},
            'premium': {'price_min': 500},
            'luxury': {'price_min': 500},
            'expensive': {'price_min': 500},
            'high-end': {'price_min': 1000},
        }

    def predict(self, query: str) -> Dict[str, Any]:
        logger.info(f"🔧 HybridConstraintPredictor.predict for: '{query}'")

        # 1. Get explicit numbers
        explicit_price = self.price_extractor.extract(query)
        explicit_rating = self.rating_extractor.extract(query)
        logger.info(f"   Explicit price: {explicit_price}")
        logger.info(f"   Explicit rating: {explicit_rating}")

        constraints = {}
        constraints.update(explicit_price)
        constraints.update(explicit_rating)

        # 2. If still no price constraints, try qualitative mapping
        if 'price_min' not in constraints and 'price_max' not in constraints:
            text_lower = query.lower()
            for term, mapping in self.qualitative_price.items():
                if term in text_lower:
                    if 'price_min' in mapping:
                        constraints['price_min'] = mapping['price_min']
                        logger.info(f"💰 Qualitative min price from '{term}': ${mapping['price_min']}")
                    if 'price_max' in mapping:
                        constraints['price_max'] = mapping['price_max']
                        logger.info(f"💰 Qualitative max price from '{term}': ${mapping['price_max']}")
                    break

        # 3. Detect sort intents - comprehensive
        q_lower = query.lower()
        
        # Price sort
        if any(word in q_lower for word in ['cheapest', 'lowest price', 'least expensive', 'most affordable', 'least costly']):
            constraints['price_sort'] = 'asc'
            logger.info("📊 Detected price sort: low to high (ascending)")
        elif any(word in q_lower for word in ['most expensive', 'highest price', 'priciest', 'most costly']):
            constraints['price_sort'] = 'desc'
            logger.info("📊 Detected price sort: high to low (descending)")

        # Rating sort
        if any(word in q_lower for word in ['highest rated', 'best rated', 'top rated', 'highest rating', 'best rating']):
            constraints['rating_sort'] = 'desc'
            logger.info("📊 Detected rating sort: high to low (descending)")
        elif any(word in q_lower for word in ['lowest rated', 'worst rated', 'lowest rating', 'bottom rated']):
            constraints['rating_sort'] = 'asc'
            logger.info("📊 Detected rating sort: low to high (ascending)")

        logger.info(f"🔧 Final constraints: {constraints}")
        return constraints