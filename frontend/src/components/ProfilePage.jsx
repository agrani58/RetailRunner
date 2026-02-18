import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import "../styles/ProfilePage.css";

export default function ProfilePage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Profile key tied to email to support multiple users
  const PROFILE_STORAGE_KEY = `user_profile_${user?.email}`;

  const [formData, setFormData] = useState({
    name: "",
    phone: "",
    address: "",
    city: "",
    postalCode: "",
    country: "",
    email: user?.email || "",
  });
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");

  // Load profile from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setFormData((prev) => ({ ...prev, ...parsed }));
      } catch (e) {
        console.error("Failed to parse profile", e);
      }
    }
  }, [PROFILE_STORAGE_KEY]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsSaving(true);

    setTimeout(() => {
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(formData));
      setIsSaving(false);
      setMessage("Profile saved successfully!");
      setTimeout(() => setMessage(""), 3000);
    }, 500);
  };

  return (
    <div className="profile-container">
      <div className="profile-card">
        <h1>Edit Profile</h1>
        {message && <div className="profile-message">{message}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label>Name</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="Your name"
            />
          </div>

          <div className="form-group">
            <label>Phone</label>
            <input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              placeholder="Phone number"
            />
          </div>

          <div className="form-group">
            <label>Address</label>
            <input
              type="text"
              name="address"
              value={formData.address}
              onChange={handleChange}
              placeholder="Street address"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>City</label>
              <input
                type="text"
                name="city"
                value={formData.city}
                onChange={handleChange}
                placeholder="City"
              />
            </div>

            <div className="form-group">
              <label>Postal Code</label>
              <input
                type="text"
                name="postalCode"
                value={formData.postalCode}
                onChange={handleChange}
                placeholder="Postal code"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Country</label>
            <input
              type="text"
              name="country"
              value={formData.country}
              onChange={handleChange}
              placeholder="Country"
            />
          </div>

          <div className="profile-actions">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="cancel-btn"
            >
              Cancel
            </button>
            <button type="submit" disabled={isSaving} className="save-btn">
              {isSaving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
