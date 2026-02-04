// components/Sidebar.jsx
import { useState } from "react";
import "../styles/Sidebar.css";

export default function Sidebar({ toggleTheme }) {
  const [showUser, setShowUser] = useState(false);

  return (
    <>
      <aside className="sidebar">
        {/* TOP ICONS */}
        <div className="sidebar-top">
          <button className="sidebar-icon" aria-label="Home">
            <svg viewBox="0 0 24 24">
              <rect x="3" y="3" width="18" height="18" rx="4" />
            </svg>
          </button>

          <button className="sidebar-icon" aria-label="Cart">
            <svg viewBox="0 0 24 24">
              <circle cx="9" cy="21" r="1" />
              <circle cx="20" cy="21" r="1" />
              <path d="M1 1h4l2.6 13.4a2 2 0 0 0 2 1.6h9.4a2 2 0 0 0 2-1.6L23 6H6" />
            </svg>
          </button>
        </div>

        {/* BOTTOM ICONS */}
        <div className="sidebar-bottom">
          {/* THEME TOGGLE */}
          <button
            className="sidebar-icon"
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            <svg viewBox="0 0 24 24">
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
            </svg>
          </button>

          {/* USER PROFILE */}
          <button
            className="sidebar-icon"
            aria-label="User"
            onClick={() => setShowUser(v => !v)}
          >
            <svg viewBox="0 0 24 24">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </button>
        </div>
      </aside>

      {/* USER OVERLAY */}
      {showUser && <UserOverlay onClose={() => setShowUser(false)} />}
    </>
  );
}
