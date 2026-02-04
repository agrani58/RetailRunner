import { useState, useCallback } from "react";
import { sendMessageToAPI } from "../api/chat";

export default function useChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return;

    setError(null);

    // Add user message
    const userMessage = {
      role: "user",
      text: text,
      timestamp: new Date().toISOString()
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Call real API
      const data = await sendMessageToAPI(text);
      
      // Add assistant response
      const assistantMessage = {
        role: "assistant",
        text: data.response || `Here are some results for "${text}"`,
        timestamp: new Date().toISOString()
      };

      // Add products if they exist
      const newMessages = [...messages, userMessage, assistantMessage];
      
      if (data.products && data.products.length > 0) {
        const productsMessage = {
          role: "products",
          products: data.products,
          timestamp: new Date().toISOString(),
          count: data.products.length
        };
        newMessages.push(productsMessage);
      }

      setMessages(newMessages);

    } catch (err) {
      console.error("Error sending message:", err);
      setError(err.message);
      
      // Add error message
      const errorMessage = {
        role: "assistant",
        text: "Sorry, I encountered an error. Please try again.",
        timestamp: new Date().toISOString(),
        isError: true
      };
      
      setMessages((prev) => [...prev, errorMessage]);
      
    } finally {
      setIsLoading(false);
    }
  }, [messages]);

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
    isEmpty: messages.length === 0 && !isLoading
  };
}