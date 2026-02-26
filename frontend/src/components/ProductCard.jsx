// frontend/src/components/ProductCard.jsx
import React, { useState } from "react";
import "../styles/ProductCard.css";

const ProductCard = ({ product, onBuyNow }) => {  // ← add onBuyNow prop
  const [imageError, setImageError] = useState(false);
  
  if (!product) return null;

  // Get the best possible image URL from product data
  const getImageUrl = () => {
    const possibleUrls = [
      product.image_url,
      product.image,
      product.img,
      product.thumbnail,
      product.photo
    ].filter(url => url && typeof url === "string" && url.trim() !== "");
    
    return possibleUrls.length > 0 ? possibleUrls[0] : null;
  };

  const imageUrl = getImageUrl();

  const handleBuyClick = (e) => {
    e.stopPropagation(); // prevent card click if you have one
    onBuyNow(product);
  };

  return (
    <div className="product-card-simple">
      {/* IMAGE CONTAINER */}
      <div className="product-image-container-simple">
        {imageUrl ? (
          <>
            <img
              src={imageUrl}
              alt={product.name || "Product image"}
              className={`product-image-simple ${imageError ? 'image-error' : ''}`}
              loading="lazy"
              onError={() => setImageError(true)}
              onLoad={() => setImageError(false)}
            />
            <div className="store-badge-simple">
              {product.store || "Store"}
            </div>
          </>
        ) : (
          <div className="no-image-placeholder">
            <div className="no-image-icon">🖼️</div>
            <div className="no-image-text">No Image</div>
            <div className="no-image-store">{product.store || "Store"}</div>
          </div>
        )}
      </div>

      {/* PRODUCT INFO */}
      <div className="product-info-simple">
        <h3 className="product-name-simple">
          {product.name || "Unnamed Product"}
        </h3>
        
        <div className="product-category-simple">
          {product.category || "Uncategorized"}
        </div>
        
        <div className="product-description-simple">
          {product.description ? 
            (product.description.length > 80 ? 
              `${product.description.substring(0, 80)}...` : 
              product.description) : 
            "No description available"}
        </div>

        <div className="product-footer-simple">
          <div className="product-price-simple">
            ${product.price ? Number(product.price).toFixed(2) : "0.00"}
          </div>
          
          <div className="product-rating-simple">
            ⭐ {product.rating || "0.0"} ({product.reviews || 0})
          </div>
        </div>

        {/* NEW: BUY NOW BUTTON */}
        <button 
          className="buy-now-btn"
          onClick={handleBuyClick}
        >
          Buy Now
        </button>
      </div>
    </div>
  );
};

export default ProductCard;