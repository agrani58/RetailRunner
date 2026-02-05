import torch
import torch.nn as nn
from sentence_transformers import SentenceTransformer


class IntentClassifier(nn.Module):
    def __init__(self, class_names, device="cpu"):
        super().__init__()
        self.device = device
        self.class_names = class_names

        self.encoder = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            device=device
        )

        embedding_dim = self.encoder.get_sentence_embedding_dimension()

        # 🔥 MUST MATCH TRAINING ARCHITECTURE EXACTLY
        self.classifier = nn.Sequential(
            nn.Linear(embedding_dim, 256),  # 0
            nn.ReLU(),                     # 1
            nn.Dropout(0.3),               # 2
            nn.Linear(256, 128),           # 3
            nn.ReLU(),                     # 4
            nn.Dropout(0.15),              # 5
            nn.Linear(128, len(class_names))# 6
        ).to(device)

        self.softmax = nn.Softmax(dim=1)

    @classmethod
    def load(cls, checkpoint_path: str, device="cpu"):
        checkpoint = torch.load(checkpoint_path, map_location=device)
        
        print(f"✅ Loading classifier from {checkpoint_path}")
        print(f"   Class names: {checkpoint.get('class_names', ['Unknown'])}")
        
        model = cls(
            class_names=checkpoint["class_names"],
            device=device
        )

        # 🔥 Handle different state dict formats
        classifier_weights = checkpoint.get("classifier_weights", 
                                          checkpoint.get("model_state_dict", 
                                                        checkpoint.get("state_dict", {})))
        
        if not classifier_weights:
            raise ValueError(f"No classifier weights found in {checkpoint_path}")
        
        # Clean state dict - handle different prefixes
        cleaned_state_dict = {}
        for k, v in classifier_weights.items():
            clean_key = k
            for prefix in ["classifier.", "module.", "model.", "classifier.module."]:
                if clean_key.startswith(prefix):
                    clean_key = clean_key.replace(prefix, "")
            cleaned_state_dict[clean_key] = v
        
        # Load state dict
        try:
            model.classifier.load_state_dict(cleaned_state_dict, strict=True)
            print("✅ State dict loaded successfully (strict=True)")
        except Exception as e:
            print(f"⚠️  Strict loading failed, trying non-strict: {e}")
            model.classifier.load_state_dict(cleaned_state_dict, strict=False)
            print("⚠️  State dict loaded (strict=False) - check for missing keys")
        
        model.eval()
        
        # Test the model with a sample
        test_result = model.predict("test query for shoes")
        print(f"✅ Model test prediction: {test_result}")
        
        return model

    def predict(self, text: str):
        with torch.no_grad():
            # Encode the text
            emb = self.encoder.encode(
                [text],
                convert_to_tensor=True,
                show_progress_bar=False
            ).to(self.device)

            # Get classifier predictions
            logits = self.classifier(emb)
            probs = self.softmax(logits)

            conf, label = torch.max(probs, dim=1)
            
            # Return detailed probabilities
            probs_list = probs.squeeze().cpu().tolist()
            
            result = {
                "label": int(label.item()),
                "confidence": float(conf.item()),
                "probs": probs_list,
                "chitchat_prob": probs_list[0] if len(probs_list) > 0 else 0.0,
                "product_prob": probs_list[1] if len(probs_list) > 1 else 0.0,
                "text_processed": text[:50] + "..." if len(text) > 50 else text
            }
            
            return result