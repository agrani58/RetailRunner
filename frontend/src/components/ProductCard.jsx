import React from 'react'
import { FiStar, FiShoppingCart } from 'react-icons/fi'
import './ProductCard.css'

const ProductCard = ({ product }) => {
  const matchPercentage = product.match_percentage || 0
  const matchColor = matchPercentage > 80 ? 'high-match' : 
                    matchPercentage > 60 ? 'medium-match' : 
                    'low-match'

  return (
    <div className="product-card fade-in">
      {/* Product Image */}
      <div className="product-image">
        {product.image_url ? (
          <img 
            src={product.image_url} 
            alt={product.name}
            className="image"
            onError={(e) => {
              e.target.onerror = null
              e.target.style.display = 'none'
            }}
          />
        ) : (
          <div className="image-placeholder">
            <FiShoppingCart className="placeholder-icon" />
          </div>
        )}
        
        {/* Match percentage badge */}
        <div className={`match-badge ${matchColor}`}>
          {matchPercentage}% match
        </div>
      </div>

      {/* Product Details */}
      <div className="product-details">
        <div className="product-header">
          <h3 className="product-name">{product.name}</h3>
          <span className="product-price">${product.price?.toFixed(2)}</span>
        </div>

        <p className="product-description">
          {product.description}
        </p>

        {/* Rating and Stock */}
        <div className="product-info">
          <div className="rating">
            <FiStar className="star-icon" />
            <span>{product.rating || 'N/A'}</span>
          </div>
          <div className={`stock-badge ${product.stock > 10 ? 'in-stock' : product.stock > 0 ? 'low-stock' : 'out-of-stock'}`}>
            {product.stock > 0 ? `${product.stock} in stock` : 'Out of stock'}
          </div>
        </div>

        {/* Category and Actions */}
        <div className="product-footer">
          <span className="product-category">{product.category}</span>
          <div className="product-actions">
            <button className="action-button cart-button">
              <FiShoppingCart />
            </button>
            <button className="action-button view-button">
              View
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProductCard