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
            nn.Linear(256, 128),            # 3
            nn.ReLU(),                     # 4
            nn.Dropout(0.15),              # 5
            nn.Linear(128, len(class_names))# 6
        ).to(device)

        self.softmax = nn.Softmax(dim=1)

    @classmethod
    def load(cls, checkpoint_path: str, device="cpu"):
        checkpoint = torch.load(checkpoint_path, map_location=device)

        model = cls(
            class_names=checkpoint["class_names"],
            device=device
        )

        # 🔥 STRIP "classifier." PREFIX
        cleaned_state_dict = {
            k.replace("classifier.", ""): v
            for k, v in checkpoint["classifier_weights"].items()
        }

        model.classifier.load_state_dict(cleaned_state_dict)
        model.eval()

        return model

    def predict(self, text: str):
        with torch.no_grad():
            emb = self.encoder.encode(
                [text],
                convert_to_tensor=True
            ).to(self.device)

            logits = self.classifier(emb)
            probs = self.softmax(logits)

            conf, label = torch.max(probs, dim=1)

            return {
                "label": int(label.item()),          # 0 or 1
                "confidence": float(conf.item()),
                "probs": probs.squeeze().cpu().tolist()
            }

