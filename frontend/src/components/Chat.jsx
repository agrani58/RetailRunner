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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-wrapper">
      <div className="chat">
        {messages.map((msg, i) => {
          if (msg.role === "products") {
            return (
              <div key={i} className="message-row product-row">
                <div className="product-list">
                  {msg.products.map((p, j) => (
                    <ProductCard key={j} product={p} />
                  ))}
                </div>
              </div>
            );
          }

          return <Message key={i} role={msg.role} text={msg.text} />;
        })}
        <div ref={bottomRef} />
      </div>

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