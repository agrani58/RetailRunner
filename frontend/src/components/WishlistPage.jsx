import React, { useState, useEffect } from 'react';
import { getWishlist, removeFromWishlist } from '../api/wishlist';
import { getOrders } from '../api/orders';
import { Link, useNavigate } from 'react-router-dom';
import ProductCard from './ProductCard';
import '../styles/WishlistPage.css';
import '../styles/ProductCard.css';

export default function WishlistPage() {
  const [wishlist, setWishlist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [removingId, setRemovingId] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchWishlist();
  }, []);

  const fetchWishlist = async () => {
    try {
      const wlData = await getWishlist();

      let orderedIds = new Set();
      let orderedNames = new Set();
      try {
        const ordersData = await getOrders();
        ordersData.forEach((o) => {
          if (o.product_id) orderedIds.add(String(o.product_id));
          if (o.name || o.product_name) {
            orderedNames.add((o.name || o.product_name).toLowerCase().trim());
          }
        });
      } catch {
        // ignore
      }

      const filtered = wlData.filter((item) => {
        const idMatch = item.product_id && orderedIds.has(String(item.product_id));
        const nameMatch =
          (item.name || item.product_name) &&
          orderedNames.has((item.name || item.product_name).toLowerCase().trim());
        return !(idMatch || nameMatch);
      });

      setWishlist(filtered);
    } catch (error) {
      console.error('Failed to load wishlist', error);
      setWishlist([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (productId) => {
    setRemovingId(productId);
    try {
      await removeFromWishlist(productId);
      setWishlist((prev) => prev.filter((item) => item.product_id !== productId));
    } catch (error) {
      console.error('Failed to remove item', error);
    } finally {
      setRemovingId(null);
    }
  };

  const handleBuyNow = (product) => {
    navigate('/', { state: { buyNowProduct: product } });
  };

  if (loading) {
    return (
      <div className="wl-loading">
        <div className="wl-spinner" />
        <p>Loading your wishlist…</p>
      </div>
    );
  }

  return (
    <div className="wl-page">
      <div className="wl-header">
        <h1>Your Wishlist</h1>
        <span className="wl-count">
          {wishlist.length} item{wishlist.length !== 1 ? 's' : ''}
        </span>
      </div>

      {wishlist.length === 0 ? (
        <div className="wl-empty">
          <div className="wl-empty-icon">❤️</div>
          <p>Your wishlist is empty. Start adding items!</p>
          <Link to="/" className="wl-cta">
            Explore Products
          </Link>
        </div>
      ) : (
        <div className="wl-grid">
          {wishlist.map((item) => (
            <div key={item.id} className="wl-card-wrapper">
              {/* Heart is hidden; trash sits at bottom-left, no overlap */}
              <ProductCard
                product={item}
                onBuyNow={handleBuyNow}
                showWishlist={false}
              />
              <button
                className={`wl-remove-btn ${
                  removingId === item.product_id ? 'wl-remove-btn--loading' : ''
                }`}
                onClick={() => handleRemove(item.product_id)}
                disabled={removingId === item.product_id}
                aria-label="Remove from wishlist"
              >
                {removingId === item.product_id ? (
                  <span className="wl-mini-spinner" />
                ) : (
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
                  </svg>
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      <Link to="/" className="wl-back">
        ← Back to Chat
      </Link>
    </div>
  );
}