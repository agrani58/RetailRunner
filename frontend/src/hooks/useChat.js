// useChat.js - Updated to properly handle intent data

import { useState } from "react";
import { sendMessageToAPI } from "../api/chat";

export default function useChat() {
  const [messages, setMessages] = useState([]);

  const sendMessage = async (text) => {
    // 1️⃣ user message
    setMessages((prev) => [
      ...prev,
      { role: "user", text }
    ]);

    try {
      // 2️⃣ API call
      const data = await sendMessageToAPI(text);

      // 3️⃣ assistant message with intent
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.response,
          intent_badge: {
            intent: data.intent_label,
            confidence: Math.round(data.intent_confidence * 100),
            level: data.intent_confidence > 0.7 ? "high" : 
                   data.intent_confidence > 0.5 ? "medium" : "low",
          },
        },
        ...(data.products && data.products.length > 0 ? [
          {
            role: "products",
            products: data.products,
          }
        ] : []),
      ]);
    } catch (error) {
      console.error("Error sending message:", error);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Sorry, I encountered an error. Please try again.",
          intent_badge: {
            intent: "error",
            confidence: 0,
            level: "low",
          },
        }
      ]);
    }
  };

  return {
    messages,
    sendMessage,
    isEmpty: messages.length === 0,
  };
}