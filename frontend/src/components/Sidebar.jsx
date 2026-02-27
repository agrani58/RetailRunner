import React, { useState, useRef, useEffect } from "react";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";
import "../styles/Sidebar.css";

export default function Sidebar({ toggleTheme }) {
  const { user, logout } = useAuth();
  const [showUserPopover, setShowUserPopover] = useState(false);
  const popoverRef = useRef(null);
  const buttonRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (buttonRef.current?.contains(e.target)) return;
      if (popoverRef.current?.contains(e.target)) return;
      setShowUserPopover(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const togglePopover = (e) => {
    e.stopPropagation();
    setShowUserPopover((prev) => !prev);
  };

  const handleEditProfile = (e) => {
    e.stopPropagation();
    setShowUserPopover(false);
    navigate("/profile");
  };

  const handleLogout = async (e) => {
    e.stopPropagation();
    setShowUserPopover(false);
    await logout();
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        {/* 1. HOME */}
        <button
          className="sidebar-icon"
          aria-label="Home"
          onClick={() => navigate("/")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="4" />
          </svg>
        </button>

        {/* 2. WISHLIST (heart) */}
        <button
          className="sidebar-icon"
          aria-label="Wishlist"
          onClick={() => navigate("/wishlist")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
          </svg>
        </button>

        {/* 3. ORDERS — receipt / list icon */}
        <button
          className="sidebar-icon"
          aria-label="Orders"
          onClick={() => navigate("/orders")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
            <path d="M8 7h8" />
            <path d="M8 11h8" />
            <path d="M8 15h5" />
          </svg>
        </button>
      </div>

      <div className="sidebar-bottom">
        {/* 4. THEME TOGGLE */}
        <button
          className="sidebar-icon"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
          </svg>
        </button>

        {/* 5. USER */}
        <div className="user-menu-container">
          <button
            ref={buttonRef}
            className="sidebar-icon"
            onClick={togglePopover}
            aria-label="User"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </button>

          {showUserPopover && user && (
            <div className="user-popover" ref={popoverRef}>
              <p className="user-email">{user.email}</p>
              <div className="user-popover-actions">
                <button className="edit-profile-btn" onClick={handleEditProfile}>
                  Edit Profile
                </button>
                <button className="logout-btn" onClick={handleLogout}>
                  Logout
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}