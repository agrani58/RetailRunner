import { useState, useCallback } from "react";
import { sendMessageToAPI } from "../api/chat";

export default function useChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return;

    setError(null);

    const userMessage = {
      role: "user",
      text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const data = await sendMessageToAPI(text);

      const assistantMessage = {
        role: "assistant",
        text: data.response || "Here's what I found.",
        intent_badge: data.intent_badge,  // Fixed: using intent_badge from response
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => {
        const updated = [...prev, assistantMessage];

        // Show products only if intent is product
        if (
          data.query_type === "product" &&
          Array.isArray(data.products) &&
          data.products.length > 0
        ) {
          const relevantProducts = data.products.filter(
            (p) => (p.match_percentage ?? 0) >= 50
          );

          if (relevantProducts.length > 0) {
            updated.push({
              role: "products",
              products: relevantProducts,
              timestamp: new Date().toISOString(),
              count: relevantProducts.length,
            });
          }
        }

        return updated;
      });

    } catch (err) {
      console.error("Error sending message:", err);
      setError(err.message);
      
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Sorry, something went wrong. Please try again.",
          isError: true,
          timestamp: new Date().toISOString(),
          intent_badge: null,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    sendMessage,
    isLoading,
    error,
    clearChat,
    isEmpty: messages.length === 0 && !isLoading,
  };
}