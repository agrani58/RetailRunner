import React from "react";
import "../styles/Message.css";

export default function Message({ role, text, intentBadge }) {
  return (
    <div className={`message-row ${role}`}>
      <div className="bubble">
        {text}

        {role === "assistant" && intentBadge && (
          <div className={`intent_badge ${intentBadge.level}`}>
            {intentBadge.intent.toUpperCase()} · {intentBadge.confidence}%
          </div>
        )}
      </div>
    </div>
  );
}