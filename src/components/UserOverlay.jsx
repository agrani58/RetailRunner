import { useState } from "react";
import UserOverlay from "./UserOverlay";
import "../styles/Sidebar.css";

export default function Sidebar() {
  const [showUser, setShowUser] = useState(false);

  return (
    <>
      <aside className="sidebar">
        <button className="icon-btn">
          {/* MENU */}
          <svg viewBox="0 0 24 24">
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>

        <button className="icon-btn">
          {/* CART */}
          <svg viewBox="0 0 24 24">
            <path d="M6 6h15l-2 9H8z" />
            <circle cx="9" cy="20" r="1" />
            <circle cx="18" cy="20" r="1" />
          </svg>
        </button>

        <div className="sidebar-spacer" />

        <button className="icon-btn">
          {/* THEME */}
          <svg viewBox="0 0 24 24">
            <path d="M21 12.8A9 9 0 1111.2 3 7 7 0 0021 12.8z" />
          </svg>
        </button>

        <button
          className="icon-btn"
          onClick={() => setShowUser((v) => !v)}
        >
          {/* PROFILE */}
          <svg viewBox="0 0 24 24">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c2-4 14-4 16 0" />
          </svg>
        </button>
      </aside>

      {showUser && <UserOverlay onClose={() => setShowUser(false)} />}
    </>
  );
}
