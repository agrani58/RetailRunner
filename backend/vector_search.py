# vector_search.py - TF-IDF Vector Search Implementation
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from typing import List, Dict, Any

class ProductSearchEngine:
    def __init__(self):
        self.products = []
        self.product_texts = []
        self.vectorizer = None
        self.product_vectors = None
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
        """Create searchable text from product attributes - STEP 1"""
        texts = []
        
        for product in products:
            # Extract all attributes
            name = product.get('name', '')
            category = product.get('category', '')
            description = product.get('description', '')
            
            # Extract keywords from name
            name_keywords = name.lower()
            
            # Extract colors from name and description
            colors = self._extract_colors(name + " " + description)
            
            # Extract materials
            materials = self._extract_materials(name + " " + description)
            
            # Extract style/type
            style = self._extract_style(name + " " + description)
            
            # Combine everything into one searchable text - STEP 1 Completed!
            search_text = f"{name_keywords} {category} {description} {colors} {materials} {style}"
            
            # Remove extra spaces
            search_text = re.sub(r'\s+', ' ', search_text.strip())
            texts.append(search_text)
        
        return texts
    
    def _extract_colors(self, text: str) -> str:
        """Extract color keywords from text"""
        colors = [
            'red', 'blue', 'green', 'yellow', 'black', 'white', 
            'gray', 'grey', 'purple', 'pink', 'orange', 'brown',
            'navy', 'maroon', 'teal', 'cyan', 'magenta', 'lavender',
            'beige', 'khaki', 'olive', 'turquoise', 'indigo', 'violet',
            'denim', 'jeans'
        ]
        
        text_lower = text.lower()
        found_colors = [color for color in colors if color in text_lower]
        
        return " ".join(found_colors)
    
    def _extract_materials(self, text: str) -> str:
        """Extract material keywords"""
        materials = [
            'leather', 'denim', 'cotton', 'wool', 'silk', 'linen',
            'polyester', 'nylon', 'spandex', 'velvet', 'suede',
            'canvas', 'fleece', 'cashmere', 'satin', 'chiffon'
        ]
        
        text_lower = text.lower()
        found_materials = [mat for mat in materials if mat in text_lower]
        
        return " ".join(found_materials)
    
    def _extract_style(self, text: str) -> str:
        """Extract style/type keywords"""
        styles = [
            'short', 'long', 'sleeve', 'sleeveless', 'hood', 'hooded',
            'casual', 'formal', 'sport', 'summer', 'winter', 'spring',
            'autumn', 'fall', 'fashion', 'vintage', 'modern', 'classic',
            'jacket', 'coat', 'shirt', 't-shirt', 'dress', 'pants',
            'jeans', 'shorts', 'skirt', 'blouse', 'sweater', 'hoodie'
        ]
        
        text_lower = text.lower()
        found_styles = [style for style in styles if style in text_lower]
        
        return " ".join(found_styles)
    
    def _train_vectorizer(self):
        """Train TF-IDF vectorizer on product texts - STEP 2"""
        # Initialize TF-IDF Vectorizer
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 3),  # Include 1-3 word combinations
            min_df=1,
            max_df=0.9,
            max_features=5000
        )
        
        # Create vectors for all products - STEP 2 Completed!
        self.product_vectors = self.vectorizer.fit_transform(self.product_texts)
        print(f"📊 Vectorizer trained with {self.product_vectors.shape[1]} features")
    
    def search(self, query: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """Search for products similar to query"""
        if not self.is_initialized_flag or self.vectorizer is None:
            raise ValueError("Search engine not initialized. Call initialize() first.")
        
        print(f"🔍 Searching for: '{query}'")
        
        # STEP 3: Transform query to vector
        query_vector = self.vectorizer.transform([query.lower()])
        
        # STEP 4: Calculate similarity scores
        similarity_scores = cosine_similarity(query_vector, self.product_vectors)
        
        # Get top N indices
        scores = similarity_scores[0]
        top_indices = np.argsort(scores)[::-1][:top_n]
        
        # STEP 5: Prepare results
        results = []
        for idx in top_indices:
            if scores[idx] > 0.05:  # Only include meaningful matches (5% threshold)
                product = self.products[idx].copy()
                product["similarity_score"] = float(scores[idx])
                product["match_percentage"] = int(scores[idx] * 100)
                
                # Get matched keywords
                product["matched_keywords"] = self._get_matched_keywords(
                    query.lower(), 
                    self.product_texts[idx]
                )
                
                results.append(product)
            else:
                print(f"⚠️ Low score ({scores[idx]:.3f}) for product index {idx}")
        
        print(f"✅ Found {len(results)} relevant products")
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