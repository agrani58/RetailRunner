// frontend/src/components/ProductCard.jsx
import React, { useState } from "react";
import "../styles/ProductCard.css";

export default function ProductCard({ product }) {
  const [imageError, setImageError] = useState(false);

  const imageUrl =
    product.image_url ||
    product.image ||
    "";

  const confidencePercentage = Math.round(product.match_percentage || 0);

  const theme = document.documentElement.dataset.theme || "light";

  const getConfidenceColor = () => {
    if (confidencePercentage >= 90) {
      return theme === "dark" ? "#10b981" : "#059669";
    }
    if (confidencePercentage >= 75) {
      return theme === "dark" ? "#f59e0b" : "#d97706";
    }
    return theme === "dark" ? "#ef4444" : "#dc2626";
  };

  const getConfidenceLabel = () => {
    if (confidencePercentage >= 90) return "Excellent Match";
    if (confidencePercentage >= 75) return "Good Match";
    return "Low Match";
  };

  const handleImageClick = () => {
    if (imageUrl) {
      window.open(imageUrl, "_blank");
    }
  };

  return (
    <div className="product-card-simple">
      <div
        className="product-image-container-simple"
        onClick={handleImageClick}
        style={{ cursor: imageUrl ? "pointer" : "default" }}
      >
        <img
          src={
            imageError || !imageUrl
              ? `https://placehold.co/300x300/1e1b18/f7f0e8?text=${encodeURIComponent(
                  product.name.substring(0, 20)
                )}`
              : imageUrl
          }
          alt={product.name}
          className="product-image-simple"
          onError={() => setImageError(true)}
          loading="lazy"
        />

        <div
          className="confidence-badge-simple"
          style={{
            backgroundColor: getConfidenceColor(),
            color: "#fff",
            border:
              theme === "dark"
                ? "2px solid rgba(255,255,255,0.1)"
                : "2px solid rgba(0,0,0,0.1)",
          }}
        >
          <div className="confidence-percent-simple">
            {confidencePercentage}%
          </div>
          <div className="confidence-label-simple">
            {getConfidenceLabel()}
          </div>
        </div>
      </div>

      <div className="product-name-simple">
        {product.name.length > 50
          ? product.name.slice(0, 50) + "…"
          : product.name}
      </div>

      <div className="product-price-simple">
        ${Number(product.price).toFixed(2)}
      </div>
    </div>
  );
}
