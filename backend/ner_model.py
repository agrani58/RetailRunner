import re
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class NERModel:
    """NER model for fashion product extraction"""
    
    def __init__(self):
        # Fashion-specific keywords
        self.product_keywords = {
            "shirt", "t-shirt", "tshirt", "blouse", "top", "polo",
            "pants", "trousers", "jeans", "denim", "leggings", "chinos",
            "jacket", "coat", "blazer", "hoodie", "sweater", "sweatshirt", "cardigan",
            "dress", "gown", "skirt", "jumpsuit", "romper",
            "shoes", "sneakers", "boots", "sandals", "heels", "flats", "footwear",
            "bag", "purse", "handbag", "backpack", "wallet", "clutch",
            "hat", "cap", "beanie", "scarf", "gloves", "belt", "tie", "bowtie",
            "jewelry", "necklace", "bracelet", "ring", "earrings", "watch",
            "sunglasses", "glasses", "eyewear", "accessories",
            "underwear", "lingerie", "socks", "stockings", "bra"
        }
        
        self.brand_keywords = {
            "nike", "adidas", "puma", "under armour", "converse", "vans",
            "levi", "levi's", "wrangler", "calvin klein", "tommy hilfiger",
            "gucci", "prada", "louis vuitton", "chanel", "dior", "hermes",
            "versace", "armani", "burberry", "ralph lauren", "zara", "hm", "h&m",
            "forever 21", "gap", "old navy", "banana republic", "uniqlo",
            "converse", "vans", "skechers", "clarks", "dr martens", "timberland",
            "ray-ban", "oakley", "prada", "versace", "michael kors", "coach"
        }
        
        self.category_keywords = {
            "jackets", "dresses", "footwear", "sweaters", "pants", 
            "accessories", "t-shirts", "coats", "shirts", "skirts",
            "bags", "jewelry", "watches", "sunglasses", "underwear",
            "activewear", "formal", "casual", "party", "evening"
        }
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text"""
        entities = {
            "product": [],
            "brand": [],
            "category": [],
            "price": [],
            "specification": []
        }
        
        text_lower = text.lower()
        
        # Extract product types
        for keyword in self.product_keywords:
            if keyword in text_lower:
                entities["product"].append(keyword)
        
        # Extract brands
        for brand in self.brand_keywords:
            if brand in text_lower:
                entities["brand"].append(brand.title())
        
        # Extract categories
        for category in self.category_keywords:
            if category in text_lower:
                entities["category"].append(category.title())
        
        # Extract price ranges
        price_patterns = [
            r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*dollars',
            r'under\s*\$\s*(\d+)',
            r'less than\s*\$\s*(\d+)',
            r'below\s*\$\s*(\d+)',
            r'over\s*\$\s*(\d+)',
            r'above\s*\$\s*(\d+)',
            r'between\s*\$\s*(\d+)\s*and\s*\$\s*(\d+)'
        ]
        
        for pattern in price_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                price_text = match.group()
                if price_text not in entities["price"]:
                    entities["price"].append(price_text)
        
        # Extract specifications
        spec_patterns = [
            r'\bleather\b',
            r'\bdenim\b',
            r'\bcotton\b',
            r'\bwool\b',
            r'\bsilk\b',
            r'\bgenuine\b',
            r'\bpremium\b',
            r'\bwaterproof\b',
            r'\bwindproof\b',
            r'\bwarm\b',
            r'\blightweight\b'
        ]
        
        for pattern in spec_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                spec = match.group()
                if spec not in entities["specification"]:
                    entities["specification"].append(spec)
        
        # If no entities found, use the query as search term
        if not any(entities.values()):
            entities["product"].append(text)
        
        # Remove duplicates
        for key in entities:
            entities[key] = list(set(entities[key]))
        
        return entities
    
    def classify_query_type(self, text: str, entities: Dict) -> Tuple[str, float]:
        """Classify the type of user query with confidence"""
        text_lower = text.lower()
        
        # Check for greetings
        greetings = ["hi", "hello", "hey", "greetings"]
        if any(greeting in text_lower for greeting in greetings):
            return "greeting", 0.95
        
        # Check for help requests
        help_terms = ["help", "what can you do", "how does this work", "assist"]
        if any(term in text_lower for term in help_terms):
            return "help", 0.90
        
        # Check for price inquiries
        price_terms = ["price", "cost", "expensive", "cheap", "how much"]
        if any(term in text_lower for term in price_terms):
            return "price_inquiry", 0.85
        
        # Check for recommendations
        recommend_terms = ["recommend", "suggest", "best", "good", "top"]
        if any(term in text_lower for term in recommend_terms):
            return "recommendation", 0.80
        
        # Check for availability questions
        availability_terms = ["in stock", "available", "shipping", "delivery"]
        if any(term in text_lower for term in availability_terms):
            return "availability", 0.75
        
        # Check if we have specific product entities
        if entities.get("product") or entities.get("brand") or entities.get("category"):
            return "product_search", 0.90
        
        # Check for general product browsing
        browse_terms = ["show me", "look for", "find", "search", "browse"]
        if any(term in text_lower for term in browse_terms):
            return "browsing", 0.65
        
        return "general", 0.50
    
    def calculate_confidence_score(self, product: Dict, search_terms: List[str], query: str) -> float:
        """Calculate confidence score for product matching"""
        score = 0.0
        query_lower = query.lower()
        
        # Product fields
        product_name = product.get("name", "").lower()
        product_description = product.get("description", "").lower()
        product_category = product.get("category", "").lower()
        
        # Split query into words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        query_words = [word for word in query_lower.split() if len(word) > 2 and word not in stop_words]
        
        # Exact name match
        for word in query_words:
            if word in product_name:
                score += 30
        
        # Category match
        for category in self.category_keywords:
            if category in query_lower and category in product_category:
                score += 20
        
        # Search terms match in description
        for term in search_terms:
            term_lower = term.lower()
            if term_lower in product_description:
                score += 15
            if term_lower in product_name:
                score += 10
        
        # Price range match
        if "under" in query_lower or "less than" in query_lower:
            price_match = re.search(r'\$?\s*(\d+)', query_lower)
            if price_match:
                try:
                    max_price = float(price_match.group(1))
                    product_price = product.get("price", 0)
                    if product_price <= max_price:
                        score += 20
                except:
                    pass
        
        # Rating boost
        product_rating = product.get("rating", 0)
        if product_rating >= 4.0:
            score += 10
        elif product_rating >= 3.0:
            score += 5
        
        # Stock availability boost
        if product.get("stock", 0) > 0:
            score += 5
        
        # Normalize and scale
        normalized_score = min(max(score, 0), 100)
        
        if normalized_score > 0:
            scaled_score = 40 + (normalized_score * 0.5)
            return min(scaled_score, 95)
        
        return 30.0
    
    def generate_search_params(self, query: str, entities: Dict) -> Dict[str, Any]:
        """Generate search parameters from extracted entities"""
        params = {}
        
        # Combine all search terms
        all_terms = []
        
        if entities.get("product"):
            all_terms.extend(entities["product"])
        
        if entities.get("brand"):
            all_terms.extend(entities["brand"])
        
        if entities.get("category"):
            all_terms.extend(entities["category"])
        
        if all_terms:
            params["q"] = " ".join(all_terms[:3])
        else:
            params["q"] = query
        
        # Extract price range
        if entities.get("price"):
            for price_text in entities["price"]:
                price_text_lower = price_text.lower()
                
                if "under" in price_text_lower or "less than" in price_text_lower:
                    price_match = re.search(r'\$?\s*(\d+)', price_text_lower)
                    if price_match:
                        try:
                            max_price = float(price_match.group(1))
                            params["max_price"] = max_price
                        except:
                            pass
        
        # Add category if specified
        if entities.get("category"):
            # Urban Threads uses capitalized categories
            params["category"] = entities["category"][0]
        
        # Add limit for number of results
        params["limit"] = 20
        
        return params