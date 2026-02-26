// frontend/src/components/OrderPasswordModal.jsx
import React, { useState } from 'react';
import { getAccessToken } from '../utils/storage';
import '../styles/OrderPasswordModal.css';

export default function OrderPasswordModal({ product, userInfo, onClose }) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  if (!product) return null;

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const fullUserInfo = { ...userInfo, password };
      const token = getAccessToken();
      const res = await fetch('http://localhost:8000/place-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({ product_name: product.name, user_info: fullUserInfo })
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Error ${res.status}`);
      }
      
      const data = await res.json();
      alert(data.message || 'Order bot started!');
      onClose();
    } catch (err) {
      alert(err.message || 'Failed to start order bot');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h1>Confirm Order</h1>
        <div className="product-details">
          <p><strong>Product:</strong> {product.name}</p>
          <p><strong>Store:</strong> {product.store || 'Unknown Store'}</p>
        </div>
        <div className="user-details">
          <p><strong>Email:</strong> {userInfo.email}</p>
          <p><strong>Name:</strong> {userInfo.name}</p>
          <p><strong>Phone:</strong> {userInfo.phone}</p>
          <p><strong>Address:</strong> {userInfo.address}</p>
        </div>
        <div className="form-group">
          <input
            type="password"
            placeholder="Enter store password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="modal-input"
          />
          <div className="password-note">
            Password for <strong>{product.store}</strong> (same email) – used only for this order.
          </div>
        </div>
        <div className="modal-actions">
          <button onClick={onClose} disabled={loading} className="cancel-btn">
            Cancel
          </button>
          <button onClick={handleSubmit} disabled={loading || !password} className="save-btn">
            {loading ? 'Starting...' : 'Place Order'}
          </button>
        </div>
      </div>
    </div>
  );
}