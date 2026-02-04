// frontend/src/components/ProductCard.jsx
import React, { useState } from "react";
import "../styles/ProductCard.css";

export default function ProductCard({ product }) {
  const [imageError, setImageError] = useState(false);
  
  const getConfidenceColor = (percentage) => {
    const theme = document.documentElement.dataset.theme || "light";
    
    if (percentage >= 90) {
      return theme === "dark" ? "#10b981" : "#059669";
    } else if (percentage >= 75) {
      return theme === "dark" ? "#f59e0b" : "#d97706";
    } else {
      return theme === "dark" ? "#ef4444" : "#dc2626";
    }
  };
  
  const getConfidenceLevel = (percentage) => {
    if (percentage >= 90) return "Excellent Match";
    if (percentage >= 75) return "Good Match";
    return "Low Match";
  };
  
  const currentTheme = document.documentElement.dataset.theme || "light";
  const confidencePercentage = Math.round(product.match_percentage || 0);
  const confidenceColor = getConfidenceColor(confidencePercentage);
  const confidenceLevel = getConfidenceLevel(confidencePercentage);
  
  const handleImageClick = () => {
    if (product.image_url && product.image_url !== "") {
      window.open(product.image_url, '_blank');
    }
  };
  
  return (
    <div className="product-card-simple">
      <div 
        className="product-image-container-simple"
        onClick={handleImageClick}
        style={{ cursor: product.image_url ? 'pointer' : 'default' }}
      >
        <img 
          src={imageError ? `https://placehold.co/300x300/1e1b18/f7f0e8?text=${encodeURIComponent(product.name.substring(0, 20))}` : product.image_url}
          alt={product.name}
          className="product-image-simple"
          onError={() => setImageError(true)}
          loading="lazy"
        />
        
        <div 
          className="confidence-badge-simple"
          style={{ 
            backgroundColor: confidenceColor,
            color: 'white',
            border: currentTheme === 'dark' ? '2px solid rgba(255,255,255,0.1)' : '2px solid rgba(0,0,0,0.1)'
          }}
        >
          <div className="confidence-percent-simple">
            {confidencePercentage}%
          </div>
          <div className="confidence-label-simple">
            {confidenceLevel}
          </div>
        </div>
      </div>
      
      <div className="product-name-simple">
        {product.name.length > 50 ? product.name.substring(0, 50) + '...' : product.name}
      </div>
      
      <div className="product-price-simple">
        ${parseFloat(product.price).toFixed(2)}
      </div>
    </div>
  );
}