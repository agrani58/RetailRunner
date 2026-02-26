// frontend/src/components/Chat.jsx (inside the product list mapping)
import React, { useState, useEffect, useRef } from "react";
import Message from "./Message";
import ProductCard from "./ProductCard";
import "../styles/Chat.css";

export default function Chat({ messages, onSend, onBuyNow }) {  // ← add onBuyNow prop
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  const send = () => {
    if (!input.trim()) return;
    onSend(input);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [input]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="chat-wrapper">
      <div className="chat">
        {messages.map((msg, i) => {
          if (msg.role === "products" || msg.products) {
            const productsToShow = msg.products || [];
            return (
              <div key={i} className="message-row product-row">
                <div className="product-list">
                  {productsToShow.map((p, j) => (
                    <ProductCard 
                      key={`${p.id}-${p.store}-${j}`} 
                      product={p} 
                      onBuyNow={onBuyNow}   // ← pass callback
                    />
                  ))}
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

      <div className="chat-input-wrapper">
        <div className="chat-input-shell">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder="Search products, brands, or deals…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button className="chat-send" onClick={send}>↑</button>
        </div>
      </div>
    </div>
  );
}