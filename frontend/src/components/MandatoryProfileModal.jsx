import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import '../styles/ProfilePage.css'; // reuse same styles

export default function MandatoryProfileModal() {
  const { user, updateProfile } = useAuth();

  const [formData, setFormData] = useState({
    name: user?.name || '',
    phone: user?.phone || '',
    address: user?.address || '',
    city: user?.city || '',
    postalCode: user?.postalCode || '',
    country: user?.country || '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Basic validation – all fields required
    if (!formData.name || !formData.phone || !formData.address || !formData.city || !formData.postalCode || !formData.country) {
      setError('All fields are required.');
      return;
    }
    setIsSaving(true);
    setError('');

    // Simulate async save (but updateProfile is synchronous)
    setTimeout(() => {
      updateProfile(formData);
      setIsSaving(false);
      // Modal will close automatically because updateProfile sets showProfileModal to false
    }, 500);
  };

  return (
    <div className="modal-overlay mandatory-modal">
      <div className="profile-card mandatory-modal-card">
        <h1>Complete Your Profile</h1>
        <p>Please fill in your details to continue. This is required only once.</p>

        {error && <div className="profile-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email (read-only)</label>
            <input
              type="email"
              value={user?.email || ''}
              disabled
            />
          </div>

          <div className="form-group">
            <label>Full Name *</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="Your name"
              required
            />
          </div>

          <div className="form-group">
            <label>Phone *</label>
            <input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              placeholder="Phone number"
              required
            />
          </div>

          <div className="form-group">
            <label>Address *</label>
            <input
              type="text"
              name="address"
              value={formData.address}
              onChange={handleChange}
              placeholder="Street address"
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>City *</label>
              <input
                type="text"
                name="city"
                value={formData.city}
                onChange={handleChange}
                placeholder="City"
                required
              />
            </div>

            <div className="form-group">
              <label>Postal Code *</label>
              <input
                type="text"
                name="postalCode"
                value={formData.postalCode}
                onChange={handleChange}
                placeholder="Postal code"
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label>Country *</label>
            <input
              type="text"
              name="country"
              value={formData.country}
              onChange={handleChange}
              placeholder="Country"
              required
            />
          </div>

          <div className="profile-actions">
            {/* No cancel button – mandatory */}
            <button type="submit" disabled={isSaving} className="save-btn">
              {isSaving ? 'Saving...' : 'Save & Continue'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}