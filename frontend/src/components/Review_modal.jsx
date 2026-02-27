import React, { useState } from 'react';
import { getAccessToken } from '../utils/storage';
import '../styles/Review_Modal.css';  // still use the same CSS file, but we'll update it

export default function ReviewModal({ order, rating, reviewText: initialReviewText, userInfo, onClose, onSubmitted }) {
  const [email, setEmail] = useState(userInfo?.email || '');
  const [displayName, setDisplayName] = useState(userInfo?.name || '');
  const [password, setPassword] = useState('');
  const [reviewText, setReviewText] = useState(initialReviewText || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!order) return null;

  const starLabel = `${rating}★`;

  const handleSubmit = async () => {
    if (!email || !password) {
      setError('Store email and password are required.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const token = getAccessToken();
      const res = await fetch('http://localhost:8000/submit-review', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({
          order_id: order.id,
          product_name: order.name || order.product_name,
          store_url: order.store_frontend_url,
          rating,
          review_text: reviewText,
          store_credentials: {
            email,
            display_name: displayName,
            password,
          },
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Error ${res.status}`);
      }

      const data = await res.json();
      alert(data.message || 'Review submitted!');
      onSubmitted(order.id);
    } catch (err) {
      setError(err.message || 'Failed to submit review');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-card">
        <h1>Submit Your Review</h1>

        {/* Product details */}
        <div className="product-details">
          <p><strong>Product:</strong> {order.name || order.product_name}</p>
          <p><strong>Store:</strong> {order.store || order.product_source || 'Store'}</p>
        </div>

        {/* Rating stars preview */}
        <div style={{ marginBottom: '16px' }}>
          <strong>Rating: </strong>
          {[1, 2, 3, 4, 5].map(s => (
            <span key={s} style={{ fontSize: '24px', color: s <= rating ? '#f59e0b' : 'var(--card-border)' }}>
              ★
            </span>
          ))}
        </div>

        {/* Review text area (optional) */}
        <div className="form-group">
          <label>Your review (optional)</label>
          <textarea
            className="modal-input"
            rows="3"
            value={reviewText}
            onChange={(e) => setReviewText(e.target.value)}
            placeholder="Share your thoughts about this product…"
            style={{ resize: 'vertical' }}
          />
        </div>

        {/* Store credentials */}
        <div className="form-group">
          <label>Store email</label>
          <input
            type="email"
            className="modal-input"
            placeholder="your@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </div>

        <div className="form-group">
          <label>Display name (optional)</label>
          <input
            type="text"
            className="modal-input"
            placeholder="How your name appears"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="name"
          />
        </div>

        <div className="form-group">
          <label>Store password</label>
          <input
            type="password"
            className="modal-input"
            placeholder="Your store account password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>

        {error && <div className="profile-error">{error}</div>}

        <div className="modal-actions">
          <button onClick={onClose} className="cancel-btn" disabled={loading}>
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="save-btn"
            disabled={loading || !email || !password}
          >
            {loading ? 'Posting…' : `Post ${starLabel} Review`}
          </button>
        </div>
      </div>
    </div>
  );
}