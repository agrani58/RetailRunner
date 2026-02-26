// frontend/src/components/OrderPasswordModal.jsx
import React, { useState } from 'react';
import '../styles/OrderPasswordModal.css';

export default function OrderPasswordModal({ product, userInfo, onClose }) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  if (!product) return null;

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const fullUserInfo = { ...userInfo, password };
      const res = await fetch('http://localhost:8000/place-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_name: product.name, user_info: fullUserInfo })
      });
      const data = await res.json();
      alert(data.message || 'Order bot started!');
      onClose();
    } catch (err) {
      alert('Failed to start order bot');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3>Confirm Order</h3>
        
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

        <input
          type="password"
          placeholder="Enter your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="modal-input"
        />

        <div className="modal-actions">
          <button 
            onClick={onClose} 
            disabled={loading}
            className="modal-btn cancel"
          >
            Cancel
          </button>
          <button 
            onClick={handleSubmit} 
            disabled={loading || !password}
            className="modal-btn confirm"
          >
            {loading ? 'Starting...' : 'Place Order'}
          </button>
        </div>
      </div>
    </div>
  );
}