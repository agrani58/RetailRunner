// frontend/src/components/Chat.jsx
import React, { useState, useEffect, useRef } from "react";
import "../styles/Chat.css";
import ProductCard from "./ProductCard";

export default function Chat({
  messages,
  onSend,
  onBuyNow,
  awaitingPaymentConfirm = false,
  onConfirmPayment,
}) {
  const [inputValue, setInputValue] = useState("");
  const chatRef    = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages, awaitingPaymentConfirm]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [inputValue]);

  const handleSend = () => {
    if (inputValue.trim()) {
      onSend(inputValue);
      setInputValue("");
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-wrapper">
      <div className="chat" ref={chatRef}>
        {messages.map((msg, i) => {
          /* ── Product grid ── */
          if (msg.role === "products") {
            return (
              <div key={i} className="message-row product-row">
                <div className="product-list">
                  {msg.products.map((product) => (
                    <ProductCard
                      key={product.id}
                      product={product}
                      onBuyNow={onBuyNow}
                    />
                  ))}
                </div>
              </div>
            );
          }

          /* ── Order confirmation ── */
          if (msg.role === "order_confirmation") {
            return (
              <div key={i} className="message-row assistant">
                <div className="bubble bubble--confirmation">
                  {msg.text}
                </div>
              </div>
            );
          }

          /* ── Bot status log ── */
          if (msg.role === "bot_status") {
            return (
              <div key={i} className="message-row bot-status">
                <div className="bubble bubble--status">
                  <span className="bot-status-icon">🤖</span>
                  {msg.text}
                </div>
              </div>
            );
          }

          /* ── Regular assistant / user messages ── */
          const cleanText = (msg.text || "")
            .replace(/\.\s*Order ID:\s*\d+/gi, ".")
            .trim();

          return (
            <div key={i} className={`message-row ${msg.role}`}>
              <div className="bubble">{cleanText}</div>
            </div>
          );
        })}

        {/* ── Confirm Payment button ── */}
        {awaitingPaymentConfirm && (
          <div className="message-row bot-status">
            <div className="bubble bubble--status bubble--payment">
              <span className="bot-status-icon">💳</span>
              <span>
                Please fill in your <strong>shipping address</strong> and{" "}
                <strong>payment details</strong> in the browser window, then
                click <em>Confirm Payment</em> below to complete your order.
              </span>
              <button
                className="confirm-payment-btn"
                onClick={onConfirmPayment}
              >
                ✅ Confirm Payment
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="chat-input-wrapper">
        <div className="chat-input-shell">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder="Ask about products…"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button className="chat-send" onClick={handleSend}>
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}