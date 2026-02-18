import os
import torch
import torch.nn as nn
from sentence_transformers import SentenceTransformer
import logging
from config import config

logger = logging.getLogger(__name__)


class IntentClassifier(nn.Module):
    def __init__(self, class_names=None, device=None):
        super().__init__()
        self.device = device or config.DEVICE
        self.class_names = class_names or ["chitchat", "product_search"]

        self.encoder = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            device=self.device
        )

        embedding_dim = self.encoder.get_sentence_embedding_dimension()

        # Classifier architecture
        self.classifier = nn.Sequential(
            nn.Linear(embedding_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(128, len(self.class_names))
        ).to(self.device)

        self.softmax = nn.Softmax(dim=1)

    @classmethod
    def load(cls, checkpoint_path: str = None, device=None):
        """Load intent classifier from checkpoint"""
        checkpoint_path = checkpoint_path or config.INTENT_MODEL_PATH
        
        if not checkpoint_path:
            raise ValueError("No checkpoint path provided")
        
        checkpoint_path = os.path.abspath(checkpoint_path)
        
        if not os.path.exists(checkpoint_path):
            # Try to find it relative to the intent model directory
            alt_path = os.path.join(config.INTENT_MODEL_DIR, 
                                   os.path.basename(checkpoint_path))
            if os.path.exists(alt_path):
                checkpoint_path = alt_path
            else:
                raise FileNotFoundError(f"❌ Checkpoint file not found: {checkpoint_path}")
        
        logger.info(f"✅ Loading intent classifier from: {checkpoint_path}")
        
        try:
            # Load checkpoint
            checkpoint = torch.load(checkpoint_path, map_location=device or config.DEVICE)
            logger.info("✅ Checkpoint loaded successfully")
        except Exception as e:
            raise RuntimeError(f"❌ Failed to load checkpoint: {e}")
        
        # Get class names
        if "class_names" in checkpoint:
            class_names = checkpoint["class_names"]
            logger.info(f"   Classes found in checkpoint: {class_names}")
        else:
            # Try to get from model_info.json if available
            model_info_path = os.path.join(os.path.dirname(checkpoint_path), "model_info.json")
            if os.path.exists(model_info_path):
                import json
                with open(model_info_path, 'r') as f:
                    model_info = json.load(f)
                    class_names = model_info.get("class_names", ["chitchat", "product_search"])
            else:
                class_names = ["chitchat", "product_search"]
            logger.warning(f"⚠️ Using default classes: {class_names}")
        
        # Create model
        model = cls(class_names=class_names, device=device or config.DEVICE)
        
        # Get state dict
        state_dict = None
        if "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        elif "classifier_weights" in checkpoint:
            state_dict = checkpoint["classifier_weights"]
        elif "classifier" in checkpoint:
            state_dict = checkpoint["classifier"]
        else:
            # Assume the checkpoint is the state dict
            state_dict = checkpoint
        
        if state_dict is None:
            raise ValueError("❌ No weights found in checkpoint")
        
        # Clean the state dict keys
        cleaned_state_dict = {}
        for key, value in state_dict.items():
            # Remove "classifier." prefix if present
            if key.startswith("classifier."):
                cleaned_key = key.replace("classifier.", "")
            # Remove "module." prefix if present (for DataParallel)
            elif key.startswith("module."):
                cleaned_key = key.replace("module.", "")
            # Remove "_orig_mod." prefix if present (for compiled models)
            elif key.startswith("_orig_mod."):
                cleaned_key = key.replace("_orig_mod.", "")
            else:
                cleaned_key = key
            
            cleaned_state_dict[cleaned_key] = value
        
        logger.info(f"✅ Cleaned state dict. Keys: {list(cleaned_state_dict.keys())[:5]}...")
        
        # Load the cleaned state dict
        try:
            model.classifier.load_state_dict(cleaned_state_dict, strict=True)
            logger.info("✅ Successfully loaded classifier weights (strict mode)")
        except Exception as e:
            logger.warning(f"⚠️ Strict loading failed: {e}. Trying non-strict loading...")
            try:
                model.classifier.load_state_dict(cleaned_state_dict, strict=False)
                logger.info("✅ Successfully loaded classifier weights (non-strict mode)")
            except Exception as e2:
                logger.error(f"❌ Non-strict loading also failed: {e2}")
                # Initialize with random weights if loading fails
                logger.warning("⚠️ Using randomly initialized classifier")
        
        model.eval()
        
        # Test the model
        try:
            test_result = model.predict("show me shoes")
            logger.info(f"🧪 Test prediction: {test_result}")
        except Exception as e:
            logger.warning(f"⚠️ Test prediction failed: {e}")
        
        return model

    def predict(self, text: str):
        with torch.no_grad():
            # Ensure text is a string
            if not isinstance(text, str):
                text = str(text)
            
            # Encode text
            emb = self.encoder.encode(
                text,
                convert_to_tensor=True,
                show_progress_bar=False
            ).to(self.device)
            
            # Reshape if needed
            if emb.dim() == 1:
                emb = emb.unsqueeze(0)
            
            # Get predictions
            logits = self.classifier(emb)
            probs = self.softmax(logits)
            
            # Get highest confidence
            conf, idx = torch.max(probs, dim=1)
            probs_list = probs.squeeze().cpu().tolist()
            
            # If probs_list is a single float (when batch size is 1), make it a list
            if isinstance(probs_list, float):
                probs_list = [probs_list]
            
            # Ensure we have valid indices
            idx_val = idx.item()
            if idx_val >= len(self.class_names):
                logger.warning(f"⚠️ Index {idx_val} out of bounds for class names ({len(self.class_names)}), using index 0")
                idx_val = 0
            
            return {
                "label": int(idx_val),
                "intent": self.class_names[idx_val],
                "confidence": float(conf.item()),
                "probs": probs_list,
                "chitchat_prob": probs_list[0] if len(probs_list) > 0 else 0.0,
                "product_prob": probs_list[1] if len(probs_list) > 1 else 0.0
            }


def load_intent_model(model_path: str = None, device=None):
    """Alternative function to load intent model with better error handling"""
    model_path = model_path or config.INTENT_MODEL_PATH
    logger.info(f"📂 Loading intent model from: {model_path}")
    
    # Check if it's a directory
    if os.path.isdir(model_path):
        # Look for the .pth file in the directory
        pth_files = [f for f in os.listdir(model_path) if f.endswith('.pth') or f.endswith('.pt')]
        if pth_files:
            # Sort by modification time (newest first)
            pth_files.sort(key=lambda f: os.path.getmtime(os.path.join(model_path, f)), reverse=True)
            model_path = os.path.join(model_path, pth_files[0])
            logger.info(f"📂 Found checkpoint file: {model_path}")
        else:
            raise FileNotFoundError(f"No .pth files found in directory: {model_path}")
    
    if not os.path.exists(model_path):
        # Try to find the model in the configured directory
        alt_path = os.path.join(config.INTENT_MODEL_DIR, os.path.basename(model_path))
        if os.path.exists(alt_path):
            model_path = alt_path
            logger.info(f"📂 Found model at configured directory: {model_path}")
        else:
            raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # Try to load using IntentClassifier.load
    try:
        model = IntentClassifier.load(model_path, device or config.DEVICE)
        return model
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        
        # Try a simpler approach - just load the checkpoint and create model
        checkpoint = torch.load(model_path, map_location=device or config.DEVICE)
        
        # Get class names
        class_names = checkpoint.get("class_names", ["chitchat", "product_search"])
        
        # Create model
        model = IntentClassifier(class_names=class_names, device=device or config.DEVICE)
        
        # Try to load state dict directly
        if "state_dict" in checkpoint:
            model.load_state_dict(checkpoint["state_dict"])
        elif "model_state_dict" in checkpoint:
            model.load_state_dict(checkpoint["model_state_dict"])
        else:
            # Try to load just the classifier part
            for key in checkpoint.keys():
                if "classifier" in key or "weight" in key or "bias" in key:
                    # Try to load this as the classifier state dict
                    try:
                        if isinstance(checkpoint[key], dict):
                            model.classifier.load_state_dict(checkpoint[key])
                        break
                    except:
                        pass
        
        model.eval()
        return model


# Convenience function to load intent model with config
def get_intent_model():
    """Get the intent model using configuration"""
    try:
        model = load_intent_model()
        return model
    except Exception as e:
        logger.error(f"Failed to load intent model: {e}")
        return None