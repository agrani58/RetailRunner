# vector_search.py - IMPROVED VERSION
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from typing import List, Dict, Any
import time

class ProductSearchEngine:
    def __init__(self):
        self.products = [] # Stores original product data
        self.product_texts = [] # Stores processed text for each product
        self.vectorizer = None  # TF-IDF model
        self.product_vectors = None # Numeric vectors of products
        self.is_initialized_flag = False
    
    def is_initialized(self) -> bool:
        return self.is_initialized_flag
    
    def initialize(self, products: List[Dict[str, Any]]):
        """Initialize the search engine with products"""
        print(f"🔄 Initializing search engine with {len(products)} products...")
        self.products = products
        self.product_texts = self._create_product_texts(products)
        self._train_vectorizer()
        self.is_initialized_flag = True
        print("✅ Search engine initialized!")
    
    def update_products(self, products: List[Dict[str, Any]]):
        """Update products and retrain vectorizer"""
        print(f"🔄 Updating search engine with {len(products)} products...")
        self.products = products
        self.product_texts = self._create_product_texts(products)
        self._train_vectorizer()
        print("✅ Search engine updated!")
    
    def _create_product_texts(self, products: List[Dict[str, Any]]) -> List[str]:
        """Create searchable text from product attributes"""
        texts = []
        
        for product in products:
            # Extract all attributes with weights
            name = product.get('name', '') * 3  # Name is most important
            category = product.get('category', '') * 2  # Category is important
            description = product.get('description', '')
            
            # Extract and weight keywords
            name_keywords = name.lower()
            
            # Extract colors, materials, styles with repetition for importance
            colors = self._extract_colors(name + " " + description) * 2
            materials = self._extract_materials(name + " " + description) * 2
            style = self._extract_style(name + " " + description) * 2
            
            # Combine everything into one searchable text
            search_text = f"{name_keywords} {category} {description} {colors} {materials} {style}"
            
            # Remove extra spaces and normalize
            search_text = re.sub(r'\s+', ' ', search_text.strip().lower())
            texts.append(search_text)
        
        return texts
    
    def _extract_colors(self, text: str) -> str:
        """Extract color keywords from text"""
        colors = [
            'red', 'blue', 'green', 'yellow', 'black', 'white', 
            'gray', 'grey', 'purple', 'pink', 'orange', 'brown',
            'navy', 'maroon', 'teal', 'cyan', 'magenta', 'lavender',
            'beige', 'khaki', 'olive', 'turquoise', 'indigo', 'violet',
            'denim', 'jeans', 'gold', 'silver'
        ]
        
        text_lower = text.lower()
        found_colors = [color for color in colors if color in text_lower]
        
        # Repeat colors for higher weight
        return " ".join(found_colors * 2)
    
    def _extract_materials(self, text: str) -> str:
        """Extract material keywords"""
        materials = [
            'leather', 'denim', 'cotton', 'wool', 'silk', 'linen',
            'polyester', 'nylon', 'spandex', 'velvet', 'suede',
            'canvas', 'fleece', 'cashmere', 'satin', 'chiffon',
            'wool', 'knit', 'woven', 'fabric'
        ]
        
        text_lower = text.lower()
        found_materials = [mat for mat in materials if mat in text_lower]
        
        return " ".join(found_materials * 2)
    
    def _extract_style(self, text: str) -> str:
        """Extract style/type keywords"""
        styles = [
            'short', 'long', 'sleeve', 'sleeveless', 'hood', 'hooded',
            'casual', 'formal', 'sport', 'summer', 'winter', 'spring',
            'autumn', 'fall', 'fashion', 'vintage', 'modern', 'classic',
            'jacket', 'coat', 'shirt', 't-shirt', 'dress', 'pants',
            'jeans', 'shorts', 'skirt', 'blouse', 'sweater', 'hoodie',
            'boots', 'shoes', 'sneakers', 'handbag', 'bag', 'accessory',
            'running', 'hiking', 'training', 'workout', 'swim', 'swimsuit'
        ]
        
        text_lower = text.lower()
        found_styles = [style for style in styles if style in text_lower]
        
        return " ".join(found_styles * 2)
    
    def _train_vectorizer(self):
        """Train TF-IDF vectorizer on product texts"""
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),  # Simpler n-grams for faster matching
            min_df=1,
            max_df=0.8,
            max_features=2000,  # Reduced for speed
            analyzer='word',
            norm='l2',
            use_idf=True,
            smooth_idf=True,
            sublinear_tf=True
        )
        
        # Create vectors for all products
        self.product_vectors = self.vectorizer.fit_transform(self.product_texts)
        print(f"📊 Vectorizer trained with {self.product_vectors.shape[1]} features")
    
    def search(self, query: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """Search for products similar to query"""
        if not self.is_initialized_flag or self.vectorizer is None:
            raise ValueError("Search engine not initialized. Call initialize() first.")
        
        print(f"🔍 Searching for: '{query}'")
        start_time = time.time()
        
        # Preprocess query
        query_lower = query.lower().strip()
        
        # Special handling for greetings and simple queries
        greeting_words = ['hi', 'hello', 'hey', 'greetings', 'how are you']
        if any(word in query_lower for word in greeting_words):
            print("👋 Detected greeting query")
            # Return all products for greetings
            results = self.products[:top_n]
            for i, product in enumerate(results):
                product = product.copy()
                product["similarity_score"] = 0.5 - (i * 0.1)  # Fake scores
                product["match_percentage"] = int((0.5 - (i * 0.1)) * 100)
                product["matched_keywords"] = ["welcome", "products"]
                results[i] = product
            return results
        
        # STEP 1: Transform query to vector
        try:
            query_vector = self.vectorizer.transform([query_lower])
        except Exception as e:
            print(f"⚠️ Error transforming query: {e}")
            # Fallback to keyword matching
            return self._fallback_search(query_lower, top_n)
        
        # STEP 2: Calculate similarity scores
        similarity_scores = cosine_similarity(query_vector, self.product_vectors)
        
        # STEP 3: Get top N indices
        scores = similarity_scores[0]
        
        # Adjust threshold dynamically based on query length
        threshold = 0.02  # Lower threshold for better matching
        
        # Get indices with scores above threshold
        valid_indices = [i for i, score in enumerate(scores) if score > threshold]
        
        if not valid_indices:
            print("⚠️ No products above threshold, showing top matches")
            # If no products above threshold, show top N regardless
            top_indices = np.argsort(scores)[::-1][:top_n]
        else:
            # Sort valid indices by score
            valid_indices.sort(key=lambda i: scores[i], reverse=True)
            top_indices = valid_indices[:top_n]
        
        # STEP 4: Prepare results
        results = []
        for idx in top_indices:
            product = self.products[idx].copy()
            score = float(scores[idx])
            
            # Boost score for exact matches in name or category
            product_name = product.get('name', '').lower()
            product_category = product.get('category', '').lower()
            
            # Check for exact word matches
            query_words = set(re.findall(r'\b\w+\b', query_lower))
            name_words = set(re.findall(r'\b\w+\b', product_name))
            category_words = set(re.findall(r'\b\w+\b', product_category))
            
            # Boost score for direct matches
            if query_words.intersection(name_words):
                score = min(score * 1.5, 1.0)
            if query_words.intersection(category_words):
                score = min(score * 1.3, 1.0)
            
            product["similarity_score"] = score
            product["match_percentage"] = int(score * 100)
            
            # Get matched keywords
            product["matched_keywords"] = self._get_matched_keywords(
                query_lower, 
                self.product_texts[idx]
            )
            
            results.append(product)
        
        elapsed_time = time.time() - start_time
        print(f"✅ Found {len(results)} relevant products in {elapsed_time:.2f}s")
        
        # Sort by similarity score
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return results
    
    def _fallback_search(self, query: str, top_n: int) -> List[Dict[str, Any]]:
        """Fallback search using simple keyword matching"""
        print(f"🔍 Using fallback search for: '{query}'")
        
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        query_words = query_words - stop_words
        
        scored_products = []
        
        for product in self.products:
            score = 0
            matched_keywords = []
            
            # Check name
            name = product.get('name', '').lower()
            name_words = set(re.findall(r'\b\w+\b', name))
            name_matches = query_words.intersection(name_words)
            if name_matches:
                score += len(name_matches) * 2
                matched_keywords.extend(list(name_matches))
            
            # Check category
            category = product.get('category', '').lower()
            category_words = set(re.findall(r'\b\w+\b', category))
            category_matches = query_words.intersection(category_words)
            if category_matches:
                score += len(category_matches) * 1.5
                matched_keywords.extend(list(category_matches))
            
            # Check description
            description = product.get('description', '').lower()
            desc_words = set(re.findall(r'\b\w+\b', description))
            desc_matches = query_words.intersection(desc_words)
            if desc_matches:
                score += len(desc_matches)
                matched_keywords.extend(list(desc_matches))
            
            if score > 0:
                product_copy = product.copy()
                product_copy["similarity_score"] = min(score / 10, 1.0)  # Normalize
                product_copy["match_percentage"] = int(min(score / 10, 1.0) * 100)
                product_copy["matched_keywords"] = list(set(matched_keywords))[:3]
                scored_products.append((score, product_copy))
        
        # Sort by score
        scored_products.sort(key=lambda x: x[0], reverse=True)
        
        # Return top N
        results = [p[1] for p in scored_products[:top_n]]
        
        # If no matches found, return random products
        if not results:
            print("⚠️ No matches found, showing random products")
            import random
            random_products = random.sample(self.products, min(top_n, len(self.products)))
            for i, product in enumerate(random_products):
                product = product.copy()
                product["similarity_score"] = 0.1
                product["match_percentage"] = 10
                product["matched_keywords"] = ["featured"]
                random_products[i] = product
            return random_products
        
        return results
    
    def _get_matched_keywords(self, query: str, product_text: str) -> List[str]:
        """Extract matching keywords between query and product"""
        # Simple keyword matching
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        product_words = set(re.findall(r'\b\w+\b', product_text.lower()))
        
        # Common stop words to ignore
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 
            'to', 'for', 'of', 'with', 'by', 'is', 'am', 'are', 'was',
            'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do',
            'does', 'did', 'will', 'would', 'shall', 'should', 'can',
            'could', 'may', 'might', 'must', 'i', 'you', 'he', 'she',
            'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
        
        # Find common words excluding stop words
        common_words = query_words.intersection(product_words) - stop_words
        
        # Return top 3 keywords
        return list(common_words)[:3]