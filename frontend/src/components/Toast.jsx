import React from "react";
import { useNavigate } from "react-router-dom";
import "../styles/Toast.css";

export default function Toast({ message, onConfirm, onDismiss }) {
  const navigate = useNavigate();

  const handleConfirm = () => {
    onConfirm();
    navigate("/profile"); // ✅ navigate to profile
  };

  return (
    <div className="toast">
      <div className="toast-content">
        <span>{message}</span>
      </div>

      <div className="toast-actions">
        <button className="toast-confirm" onClick={handleConfirm}>
          Yes, update
        </button>
        <button className="toast-dismiss" onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    </div>
  );
}