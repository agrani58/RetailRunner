// frontend/src/components/UserOverlay.jsx
import React from "react";
import { useState } from "react";
import "../styles/Sidebar.css";

import "../styles/UserOverlay.css";

export default function UserOverlay({ onClose }) {
  return (
    <>
      <div className="overlay-backdrop" onClick={onClose} />
      <div className="user-overlay-fixed">
        <div className="user-card">
          <div className="user-header">
            <div className="avatar">U</div>
            <div>
              <h3>User Name</h3>
              <p>user@example.com</p>
            </div>
          </div>
          <button className="primary">View Profile</button>
          <button className="secondary">Settings</button>
          <button className="secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </>
  );
}