// frontend/src/components/Chat.jsx
import React, { useState, useEffect, useRef } from "react";
import Message from "./Message";
import ProductCard from "./ProductCard";
import "../styles/Chat.css";

export default function Chat({ messages, onSend }) {
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);

  const send = () => {
    if (!input.trim()) return;
    onSend(input);
    setInput("");
  };

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end"
    });
  }, [messages]);

  return (
    <div className="chat-wrapper">
      <div className="chat">
        {messages.map((msg, i) => {
          // Debug: Log each message
          console.log(`Message ${i}:`, msg);
          
          if (msg.role === "products" || msg.products) {
            const productsToShow = msg.products || [];
            console.log(`Rendering ${productsToShow.length} products`);
            
            return (
              <div key={i} className="message-row product-row">
                <div className="product-list">
                  {productsToShow.map((p, j) => {
                    console.log(`Product ${j}:`, p);
                    return <ProductCard key={`${p.id}-${p.store}-${j}`} product={p} />;
                  })}
                </div>
              </div>
            );
          }

          return (
            <Message
              key={i}
              role={msg.role}
              text={msg.text}
              intentBadge={msg.intent_badge}
            />
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Floating input */}
      <div className="chat-input-wrapper">
        <div className="chat-input-shell">
          <input
            className="chat-input"
            placeholder="Search products, brands, or deals…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button className="chat-send" onClick={send}>↑</button>
        </div>
      </div>
    </div>
  );
}