import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import '../styles/ProfilePage.css';

export default function MandatoryProfileModal() {
  const { user, updateProfile } = useAuth();

  const [formData, setFormData] = useState({
    name:       user?.name       || '',
    phone:      user?.phone      || '',
    address:    user?.address    || '',
    city:       user?.city       || '',
    postalCode: user?.postalCode || '',
    country:    user?.country    || '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [error,    setError]    = useState('');

  const handleChange = (e) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const { name, phone, address, city, postalCode, country } = formData;
    if (!name || !phone || !address || !city || !postalCode || !country) {
      setError('All fields are required.');
      return;
    }

    setError('');
    setIsSaving(true);

    // updateProfile persists to localStorage and sets showProfileModal=false
    // It never clears tokens, so the user stays logged in.
    setTimeout(() => {
      updateProfile(formData);
      setIsSaving(false);
    }, 300);
  };

  return (
    <div className="modal-overlay mandatory-modal">
      <div className="profile-card mandatory-modal-card">
        <h1>Complete Your Profile</h1>
        <p>Please fill in your details to continue. You can edit them later from your profile.</p>

        {error && <div className="profile-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email (read-only)</label>
            <input type="email" value={user?.email || ''} disabled />
          </div>

          <div className="form-group">
            <label>Full Name *</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="Your full name"
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
            <label>Street Address *</label>
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
            <button type="submit" disabled={isSaving} className="save-btn">
              {isSaving ? 'Saving…' : 'Save & Continue'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}