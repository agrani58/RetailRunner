import "../styles/ProductCard.css";

export default function ProductCard({ product }) {
  // Calculate confidence color
  const getConfidenceColor = (percentage) => {
    if (percentage >= 80) return "#10b981"; // Green
    if (percentage >= 60) return "#f59e0b"; // Yellow
    if (percentage >= 40) return "#f97316"; // Orange
    return "#ef4444"; // Red
  };

  return (
    <div className="product-card">
      <div className="product-image-container">
        <img 
          src={product.image_url || "/api/placeholder/200/200"} 
          alt={product.name}
          className="product-image"
          onError={(e) => {
            e.target.src = "/api/placeholder/200/200";
          }}
        />
        {product.match_percentage && (
          <div 
            className="confidence-badge"
            style={{ backgroundColor: getConfidenceColor(product.match_percentage) }}
          >
            {Math.round(product.match_percentage)}% match
          </div>
        )}
      </div>
      <div className="product-info">
        <h4 className="product-name">{product.name}</h4>
        <p className="product-description">{product.description?.substring(0, 60)}...</p>
        <div className="product-meta">
          <div className="price-section">
            <span className="price">${product.price.toFixed(2)}</span>
            {product.rating > 0 && (
              <div className="rating">
                ⭐ {product.rating.toFixed(1)} ({product.review_count || 0})
              </div>
            )}
          </div>
          <div className="stock-info">
            {product.stock > 0 ? (
              <span className="in-stock">✓ In Stock</span>
            ) : (
              <span className="out-of-stock">✗ Out of Stock</span>
            )}
          </div>
        </div>
        <button className="add-to-cart-btn">Add to Cart</button>
      </div>
    </div>
  );
}