// frontend/src/components/Home.jsx
import React, { useState } from "react";
import useChat from "../hooks/useChat";
import { useAuth } from "../hooks/useAuth";
import Landing from "./Landing";
import Chat from "./Chat";
import OrderPasswordModal from "./OrderPasswordModal";

export default function Home() {
  const { user } = useAuth();
  const [orderModal, setOrderModal] = useState({ visible: false, product: null, userInfo: {} });

  const handlePlaceOrder = (product, userInfo) => {
    setOrderModal({ visible: true, product, userInfo });
  };

  const handleBuyNow = (product) => {
    if (!user) {
      alert("Please log in first");
      return;
    }
    handlePlaceOrder(product, {
      name: user.name || '',
      email: user.email,
      phone: user.phone || '',
      address: user.address || ''
    });
  };

  const { messages, sendMessage, isEmpty } = useChat(user, handlePlaceOrder);

  return (
    <>
      {isEmpty ? (
        <Landing onSend={sendMessage} />
      ) : (
        <Chat 
          messages={messages} 
          onSend={sendMessage} 
          onBuyNow={handleBuyNow}
        />
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