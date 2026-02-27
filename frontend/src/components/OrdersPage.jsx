import React, { useState, useEffect } from 'react';
import { getOrders } from '../api/orders';
import { Link, useNavigate } from 'react-router-dom';
import ReviewModal from './Review_modal';
import { useAuth } from '../hooks/useAuth';
import ProductCard from './ProductCard';
import '../styles/OrdersPage.css';
import '../styles/ProductCard.css';

function shouldHide(order) {
  if (!order.reviewed) return false;
  const orderDate = order.order_date ? new Date(order.order_date) : null;
  if (!orderDate) return false;
  const oneWeekMs = 7 * 24 * 60 * 60 * 1000;
  return Date.now() - orderDate.getTime() > oneWeekMs;
}

/**
 * Normalise an order object into the shape ProductCard expects.
 * Orders come back from the API with various field names — this ensures
 * name, category, description, price, image_url, store are always set.
 */
function orderToProduct(order) {
  return {
    id:          order.id,
    name:        order.name || order.product_name || 'Unknown Product',
    category:    order.category || order.product_category || order.product_type || '',
    description: order.description || order.product_description || '',
    price:       order.price ?? order.product_price ?? 0,
    image_url:   order.image_url || order.image || order.thumbnail || order.photo || null,
    store:       order.store || order.product_source || order.store_name || 'Store',
    rating:      order.rating ?? order.product_rating ?? null,
    reviews:     order.reviews ?? order.review_count ?? null,
  };
}

export default function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reviewTarget, setReviewTarget] = useState(null);
  const [hoverRatings, setHoverRatings] = useState({});
  const [selectedRatings, setSelectedRatings] = useState({});
  const [showTextArea, setShowTextArea] = useState({});
  const [reviewTexts, setReviewTexts] = useState({});
  const navigate = useNavigate();
  const { user } = useAuth();

  useEffect(() => {
    getOrders()
      .then((data) => {
        setOrders(data.filter((o) => !shouldHide(o)));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleStarClick = (orderId, star) => {
    setSelectedRatings((prev) => ({ ...prev, [orderId]: star }));
    setShowTextArea((prev) => ({ ...prev, [orderId]: true }));
  };

  const handleSubmitReview = (order) => {
    const rating = selectedRatings[order.id];
    if (!rating) return;
    setReviewTarget({
      order,
      rating,
      reviewText: reviewTexts[order.id] || '',
    });
  };

  const handleModalClose = () => setReviewTarget(null);

  const handleReviewSubmitted = (orderId) => {
    setOrders((prev) =>
      prev
        .map((o) => (o.id === orderId ? { ...o, reviewed: true } : o))
        .filter((o) => !shouldHide(o))
    );
    setReviewTarget(null);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const canReview = (order) => !order.reviewed && order.store_frontend_url;

  const handleBuyAgain = (order) => {
    navigate('/', { state: { buyNowProduct: order } });
  };

  if (loading) {
    return (
      <div className="op-loading">
        <div className="op-spinner" />
        <p>Loading your orders…</p>
      </div>
    );
  }

  return (
    <div className="op-page">
      <div className="op-header">
        <h1>Your Orders</h1>
        <span className="op-count">
          {orders.length} order{orders.length !== 1 ? 's' : ''}
        </span>
      </div>

      {orders.length === 0 ? (
        <div className="op-empty">
          <div className="op-empty-icon">📦</div>
          <p>No orders yet. Start shopping!</p>
          <Link to="/" className="op-cta">
            Explore Products
          </Link>
        </div>
      ) : (
        <div className="op-grid">
          {orders.map((order) => {
            const rating = selectedRatings[order.id] || 0;
            const hover = hoverRatings[order.id] || 0;
            const displayRating = hover || rating;
            const product = orderToProduct(order);

            return (
              <div key={order.id} className="op-card-wrapper">
                <ProductCard
                  product={product}
                  onBuyNow={handleBuyAgain}
                  showWishlist={false}
                />

                <div className="order-details">
                  <div className="op-status-text">
                    {order.reviewed ? '✓ Reviewed' : 'Pending Review'}
                  </div>

                  <div className="op-dates">
                    <span>Ordered: {formatDate(order.order_date)}</span>
                    <span>Delivery: {order.delivery_date || 'N/A'}</span>
                  </div>

                  {order.reviewed ? (
                    <div className="op-reviewed-note">
                      <span>⭐ Review submitted</span>
                    </div>
                  ) : canReview(order) ? (
                    <div className="op-review-block">
                      <p className="op-review-label">Rate this product</p>
                      <div className="op-stars">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            className={`op-star ${
                              star <= displayRating ? 'op-star--on' : ''
                            }`}
                            onMouseEnter={() =>
                              setHoverRatings((prev) => ({ ...prev, [order.id]: star }))
                            }
                            onMouseLeave={() =>
                              setHoverRatings((prev) => ({ ...prev, [order.id]: 0 }))
                            }
                            onClick={() => handleStarClick(order.id, star)}
                            aria-label={`${star} star`}
                          >
                            ★
                          </button>
                        ))}
                      </div>

                      {showTextArea[order.id] && (
                        <>
                          <textarea
                            className="op-review-ta"
                            placeholder="Your thoughts (optional)…"
                            value={reviewTexts[order.id] || ''}
                            onChange={(e) =>
                              setReviewTexts((prev) => ({
                                ...prev,
                                [order.id]: e.target.value,
                              }))
                            }
                          />
                          <button
                            className="op-submit-btn"
                            onClick={() => handleSubmitReview(order)}
                          >
                            Submit Review
                          </button>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="op-no-review">
                      <span>No store link available for review</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {reviewTarget && (
        <ReviewModal
          order={reviewTarget.order}
          rating={reviewTarget.rating}
          reviewText={reviewTarget.reviewText}
          userInfo={{
            email: user?.email || '',
            name: user?.name || user?.display_name || '',
          }}
          onClose={handleModalClose}
          onSubmitted={handleReviewSubmitted}
        />
      )}

      <Link to="/" className="op-back">
        ← Back to Chat
      </Link>
    </div>
  );
}