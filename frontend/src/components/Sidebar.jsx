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
    return () =>
      document.removeEventListener("mousedown", handleClickOutside);
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
        <button
          className="sidebar-icon"
          aria-label="Home"
          onClick={() => navigate("/")}
        >
          <svg viewBox="0 0 24 24">
            <rect x="3" y="3" width="18" height="18" rx="4" />
          </svg>
        </button>
      </div>

      <div className="sidebar-bottom">
        <button
          className="sidebar-icon"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          <svg viewBox="0 0 24 24">
            <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
          </svg>
        </button>

        <div className="user-menu-container">
          <button
            ref={buttonRef}
            className="sidebar-icon"
            onClick={togglePopover}
            aria-label="User"
          >
            <svg viewBox="0 0 24 24">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </button>

          {showUserPopover && user && (
            <div className="user-popover" ref={popoverRef}>
              <p className="user-email">{user.email}</p>

              <div className="user-popover-actions">
                <button
                  className="edit-profile-btn"
                  onClick={handleEditProfile}
                >
                  Edit Profile
                </button>

                <button
                  className="logout-btn"
                  onClick={handleLogout}
                >
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
