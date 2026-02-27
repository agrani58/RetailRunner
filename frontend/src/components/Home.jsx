// frontend/src/components/Home.jsx
import React, { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import useChat from "../hooks/useChat";
import { useAuth } from "../hooks/useAuth";
import Landing from "./Landing";
import Chat from "./Chat";
import OrderPasswordModal from "./OrderPasswordModal";
import { loadMessages, saveMessages } from "../utils/chatCache"; // <-- import

export default function Home() {
  const { user } = useAuth();
  const location = useLocation();
  const [orderModal, setOrderModal] = useState({ visible: false, product: null, userInfo: {} });

  const userId = user?.id ?? user?.user_id ?? null;

  // Load initial messages from cache
  const initialRef = useRef(null);
  if (initialRef.current === null) {
    initialRef.current = loadMessages(userId);
  }

  const { messages, sendMessage, isEmpty } = useChat(
    user,
    handlePlaceOrder,
    initialRef.current,
  );

  // Persist messages to cache on every change
  useEffect(() => {
    saveMessages(userId, messages);
  }, [messages, userId]);

  // Handle buy-now triggered from Wishlist/Orders page
  useEffect(() => {
    if (location.state?.buyNowProduct) {
      const product = location.state.buyNowProduct;
      handlePlaceOrder(product, {
        name:    user?.name    || "",
        email:   user?.email   || "",
        phone:   user?.phone   || "",
        address: user?.address || "",
      });
      window.history.replaceState({}, document.title);
    }
  }, [location.state]); // eslint-disable-line react-hooks/exhaustive-deps

  function handlePlaceOrder(product, userInfo) {
    if (!user) { alert("Please log in first"); return; }
    setOrderModal({ visible: true, product, userInfo });
  }

  const handleBuyNow = (product) => {
    handlePlaceOrder(product, {
      name:    user?.name    || "",
      email:   user?.email   || "",
      phone:   user?.phone   || "",
      address: user?.address || "",
    });
  };

  return (
    <>
      {isEmpty ? (
        <Landing onSend={sendMessage} />
      ) : (
        <Chat messages={messages} onSend={sendMessage} onBuyNow={handleBuyNow} />
      )}
      {orderModal.visible && (
        <OrderPasswordModal
          product={orderModal.product}
          userInfo={orderModal.userInfo}
          onClose={() => setOrderModal({ visible: false, product: null, userInfo: {} })}
        />
      )}
    </>
  );
}