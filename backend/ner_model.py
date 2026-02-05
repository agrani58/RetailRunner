import pickle
import random
import re
import logging
from typing import Dict, List, Tuple
from rapidfuzz import fuzz
from intent_model import IntentClassifier
from preprocessing import TextPreprocessor
import inflect
from collections import Counter
import spacy

# Load spaCy model for better NLP
try:
    nlp = spacy.load("en_core_web_sm")
except:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

p = inflect.engine()

class MLNERModel:
    def __init__(self, classifier_path, preprocessor_path, device="cpu"):
        self.classifier = IntentClassifier.load(classifier_path, device=device)

        with open(preprocessor_path, "rb") as f:
            self.preprocessor: TextPreprocessor = pickle.load(f)

        self.chitchat_responses = [
            "🙂 Hey! Let me know what you're shopping for.",
            "👋 Hi there! What product are you looking for?",
            "🛍️ Just tell me what you want to buy.",
            "😉 Shopping today? I've got you covered."
        ]
        
        # Common non-product words to filter
        self.non_product_words = {
            "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
            "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
            "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
            "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are",
            "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does",
            "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until",
            "while", "of", "at", "by", "for", "with", "about", "against", "between", "into",
            "through", "during", "before", "after", "above", "below", "to", "from", "up", "down",
            "in", "out", "on", "off", "over", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few",
            "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now",
            "want", "need", "like", "looking", "search", "find", "show", "see", "buy", "get",
            "give", "make", "know", "take", "come", "look", "use", "think", "go", "see", "well",
            "also", "good", "new", "first", "last", "long", "great", "little", "old", "right",
            "big", "high", "different", "small", "large", "next", "early", "young", "important",
            "few", "public", "bad", "same", "able", "available", "popular", "basic", "sure",
            "easy", "clear", "recent", "certain", "major", "personal", "current", "national",
            "free", "open", "whole", "white", "black", "red", "green", "blue", "yellow", "brown",
            "gray", "please", "thank", "thanks", "hello", "hi", "hey", "okay", "yes", "no",
            "maybe", "ok", "well", "really", "very", "quite", "too", "just", "still", "already",
            "today", "now", "tomorrow", "yesterday", "always", "never", "sometimes", "usually",
            "often", "soon", "later", "almost", "enough", "even", "much", "many", "more", "most",
            "less", "least", "only", "just", "about", "around", "over", "under", "above", "below",
            "between", "among", "through", "across", "into", "onto", "toward", "from", "to",
            "in", "on", "at", "by", "with", "without", "for", "of", "about", "against", "during",
            "before", "after", "since", "until", "while", "because", "although", "though",
            "unless", "whether", "while", "where", "when", "why", "how", "what", "which", "who",
            "whom", "whose"
        }

    # ================ 100% INTENT MODEL USAGE ================
    def classify_query_type(self, query: str) -> Tuple[str, float, int]:
        """
        Classify query type using ONLY the ML classifier - 100% usage
        No entity-based overrides, no confidence adjustments
        """
        normalized = self.preprocessor.normalize(query)
        
        # Get classifier prediction - USE IT 100%
        result = self.classifier.predict(normalized)
        
        # Return exactly what the model says - NO MODIFICATIONS
        return (
            "product" if result["label"] == 1 else "chitchat",
            result["confidence"],  # Use model's confidence
            result["label"]        # Use model's label
        )

    # ---------------- IMPROVED NER WITH POS TAGGING ----------------
    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract product entities using spaCy POS tagging"""
        # Clean and lowercase
        query = query.lower().strip()
        
        # Skip very short queries
        if len(query) < 3:
            return {"product": [], "brand": []}
        
        # Use spaCy for better NLP processing
        doc = nlp(query)
        
        # Extract nouns, proper nouns, and adjectives (likely product-related)
        product_terms = []
        
        for token in doc:
            # Skip pronouns, determiners, aux verbs, particles, etc.
            if token.pos_ in ["PRON", "DET", "AUX", "PART", "ADP", "CCONJ", "SCONJ", "INTJ"]:
                continue
                
            # Skip common non-product words
            if token.text in self.non_product_words:
                continue
                
            # Skip short words (less than 3 chars for nouns)
            if len(token.text) < 3 and token.pos_ != "ADJ":
                continue
                
            # Skip stopwords that spaCy identifies
            if token.is_stop and token.pos_ != "NOUN":
                continue
                
            # Convert nouns to singular
            if token.pos_ in ["NOUN", "PROPN"]:
                # Skip ambiguous nouns that are often verbs
                if token.text in ["watch", "show", "run", "play", "call"]:
                    continue
                    
                singular = p.singular_noun(token.text)
                if singular:
                    product_terms.append(singular)
                else:
                    product_terms.append(token.text)
            elif token.pos_ in ["ADJ", "NUM"]:
                # Keep adjectives and numbers
                product_terms.append(token.text)
        
        # Also extract noun chunks (multi-word products)
        noun_chunks = []
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.lower()
            # Filter out chunks that are mostly stopwords
            words = chunk_text.split()
            meaningful_words = [w for w in words if w not in self.non_product_words and len(w) >= 2]
            if meaningful_words:
                # Check if chunk starts with a product word
                if meaningful_words[0] in product_terms:
                    noun_chunks.append(" ".join(meaningful_words))
        
        # Combine and deduplicate
        all_terms = list(set(product_terms + noun_chunks))
        
        # Filter: remove terms that are too generic
        final_terms = []
        for term in all_terms:
            # Skip single letters
            if len(term) <= 1:
                continue
            # Skip terms that are just numbers
            if term.isdigit():
                continue
            # Skip terms that are mostly non-alphabetic
            if sum(1 for c in term if c.isalpha()) < 2:
                continue
            # Skip terms that are too common
            if term in ["something", "anything", "everything", "nothing"]:
                continue
            final_terms.append(term)
        
        return {
            "product": final_terms,
            "brand": []
        }

    # ---------------- IMPROVED SEARCH PARAMS ----------------
    def generate_search_params(self, entities: Dict) -> Dict:
        if not entities["product"]:
            return {}
        
        # Clean up product terms: remove very short terms
        clean_terms = [term for term in entities["product"] if len(term) >= 3]
        
        if not clean_terms:
            return {}
        
        # Use the most significant term (longest) as main search
        main_term = max(clean_terms, key=len)
        
        return {
            "q": main_term,
            "limit": 20
        }

    # ---------------- CONFIDENCE ----------------
    def calculate_confidence_score(self, product, terms, query):
        if not terms:
            return 50.0
            
        product_name = product["name"].lower()
        query_lower = query.lower()
        
        scores = []
        
        # Check exact match
        for term in terms:
            if term in product_name:
                scores.append(100)
            elif term in query_lower:
                # Term from query matches something
                scores.append(80)
            else:
                # Fuzzy match
                scores.append(fuzz.token_sort_ratio(product_name, term))
        
        # Bonus for category match
        category = product.get("category", "").lower()
        if category and any(term in category for term in terms):
            scores.append(90)
        
        return max(scores) if scores else 50.0

    # ---------------- CHITCHAT ----------------
    def get_chitchat_response(self) -> str:
        return random.choice(self.chitchat_responses)