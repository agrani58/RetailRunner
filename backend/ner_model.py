import pickle
import random
from typing import Dict, List, Tuple
from rapidfuzz import fuzz
from intent_model import IntentClassifier
from preprocessing import TextPreprocessor


INTENT_CONFIDENCE_THRESHOLD = 0.70


class MLNERModel:
    def __init__(self, classifier_path, preprocessor_path, device="cpu"):
        self.device = device

        self.classifier = IntentClassifier.load(
            classifier_path,
            device=device
        )

        with open(preprocessor_path, "rb") as f:
            self.preprocessor: TextPreprocessor = pickle.load(f)

        self.chitchat_responses = [
            "🙂 Hey! Let me know what you’re shopping for.",
            "👋 Hi there! What product are you looking for?",
            "😄 I can help you find jackets, shoes, shirts and more.",
            "🛍️ Just tell me what you want to buy.",
            "✨ Ready when you are — name the product.",
            "😉 Shopping today? I’ve got you covered."
        ]

    # ---------------- INTENT ----------------
    INTENT_CONFIDENCE_THRESHOLD = 0.70

    def classify_query_type(self, query: str) -> Tuple[str, float, int]:
        normalized = self.preprocessor.normalize(query)

        # 1️⃣ ENTITY FIRST (MULTI-INTENT SUPPORT)
        entities = self.extract_entities(normalized)
        if entities.get("product"):
            return "product", 1.0, 1  # forced product intent

        # 2️⃣ FALL BACK TO MODEL
        result = self.classifier.predict(normalized)
        label = result["label"]
        confidence = result["confidence"]

        # 3️⃣ CONFIDENCE GATE
        if confidence < INTENT_CONFIDENCE_THRESHOLD:
            return "chitchat", confidence, 0

        if label == 1:
            return "product", confidence, 1

        return "chitchat", confidence, 0

    # ---------------- NER ----------------
    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        query = query.lower()
        entities = {"product": [], "brand": []}

        known_products = [
            "shirt", "tshirt", "jacket", "jeans",
            "shoes", "dress", "hoodie", "boots"
        ]

        known_brands = ["nike", "adidas", "puma", "levis"]

        for p in known_products:
            if p in query:
                entities["product"].append(p)

        for b in known_brands:
            if b in query:
                entities["brand"].append(b)

        return entities

    # ---------------- SEARCH PARAMS ----------------
    def generate_search_params(self, entities: Dict) -> Dict:
        # 🚫 ABSOLUTELY NO FALLBACK TO RAW QUERY
        if not entities["product"]:
            return {}

        params = {
            "q": " ".join(entities["product"]),
            "limit": 20
        }

        if entities["brand"]:
            params["brand"] = " ".join(entities["brand"])

        return params

    # ---------------- CONFIDENCE ----------------
    def calculate_confidence_score(self, product, terms, query):
        scores = []
        name = product["name"].lower()

        for t in terms:
            scores.append(fuzz.token_sort_ratio(name, t))

        scores.append(fuzz.token_sort_ratio(name, query.lower()))

        return sum(scores) / len(scores) if scores else 50.0

    # ---------------- CHITCHAT ----------------
    def get_chitchat_response(self) -> str:
        return random.choice(self.chitchat_responses)
