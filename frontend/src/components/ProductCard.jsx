// ProductCard.jsx
import React, { useState, useEffect } from "react";
import {
  addToWishlist,
  removeFromWishlist,
  getWishlist,
} from "../api/wishlist";
import "../styles/ProductCard.css";

const ProductCard = ({ product, onBuyNow, hideHeart }) => {
  // Guard against undefined product (e.g., from ProfilePage)
  if (!product) {
    return null; // or return a placeholder, but null prevents rendering
  }

  const [imageError, setImageError] = useState(false);
  const [isWishlisted, setIsWishlisted] = useState(false);

  useEffect(() => {
    if (hideHeart) return; // skip wishlist check if heart is hidden

    // Ensure product.id exists before checking wishlist
    if (!product.id) return;

    const checkWishlist = async () => {
      try {
        const wishlist = await getWishlist();
        const found = wishlist.find(
          (item) => String(item.product_id) === String(product.id)
        );
        setIsWishlisted(!!found);
      } catch (err) {
        console.error(err);
      }
    };
    checkWishlist();
  }, [product.id, hideHeart]); // product.id is now safe because of early return

  const toggleWishlist = async (e) => {
    e.stopPropagation();
    try {
      if (isWishlisted) {
        await removeFromWishlist(product.id);
        setIsWishlisted(false);
      } else {
        await addToWishlist({
          id: Number(product.id),
          name: product.name,
          store: product.store,
        });
        setIsWishlisted(true);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const imageUrl =
    product.image_url ||
    product.image ||
    product.thumbnail ||
    product.photo ||
    null;

  return (
    <div className="product-card">
      {/* Wishlist button (hidden if hideHeart is true) */}
      {!hideHeart && (
        <button
          className={`wishlist-btn ${isWishlisted ? "filled" : ""}`}
          onClick={toggleWishlist}
        >
          <svg viewBox="0 0 24 24">
            <path
              d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5
                 2 5.42 4.42 3 7.5 3
                 c1.74 0 3.41.81 4.5 2.09
                 C13.09 3.81 14.76 3 16.5 3
                 19.58 3 22 5.42 22 8.5
                 c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
              fill={isWishlisted ? "currentColor" : "none"}
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </svg>
        </button>
      )}

      {/* Image */}
      <div className="product-image-wrapper">
        {imageUrl && !imageError ? (
          <img
            src={imageUrl}
            alt={product.name}
            className="product-image"
            loading="lazy"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="image-placeholder">🖼️</div>
        )}

        <div className="store-badge">
          {product.store || "Store"}
        </div>
      </div>

      {/* Content */}
      <div className="product-content">
        <div className="product-title">
          {product.name || "Unnamed Product"}
        </div>

        <div className="product-category">
          {product.category || "Uncategorized"}
        </div>

        <div className="product-description">
          {product.description || "No description available"}
        </div>

        <div className="product-footer">
          <div className="product-price">
            ${Number(product.price || 0).toFixed(2)}
          </div>

          <div className="product-rating">
            ⭐ {product.rating || "0.0"} ({product.reviews || 0})
          </div>
        </div>

        <button
          className="buy-btn"
          onClick={() => onBuyNow(product)}
        >
          Buy Now
        </button>
      </div>
    </div>
  );
};

export default ProductCard;