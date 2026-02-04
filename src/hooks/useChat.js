import { useState } from "react";

export default function useChat() {
  const [messages, setMessages] = useState([]);

  const sendMessage = (text) => {
    if (!text.trim()) return;

    // user message
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text: text, // 🔑 USE `text` (matches Chat.jsx)
      },
    ]);

    // mock assistant response
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Here are some results for "${text}"`,
        },
        {
          role: "products",
          products: [
            {
              id: 1,
              name: "Wireless Headphones",
              price: 199,
            },
            {
              id: 2,
              name: "Smart Watch",
              price: 149,
            },
          ],
        },
      ]);
    }, 300);
  };

  return {
    messages,
    sendMessage,
    isEmpty: messages.length === 0,
  };
}
