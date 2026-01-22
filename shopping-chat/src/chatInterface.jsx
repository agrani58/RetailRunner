// frontend/src/ChatInterface.jsx
import React, { useState, useRef, useEffect } from "react";

export default function ChatInterface({ sendMessage }) {
  const [messages, setMessages] = useState([
    { role: "system", content: "Hi! I'm your shopping assistant. Ask me for products like 'blue denim jacket' or 'summer dresses'." },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await sendMessage(input);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response },
      ]);
    } catch (error) {
      console.error("Error:", error);
      setMessages((prev) => [
        ...prev,
        { 
          role: "assistant", 
          content: "Sorry, I encountered an error. Please try again." 
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleExampleClick = (example) => {
    setInput(example);
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-b from-gray-50 to-blue-50">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 px-6 text-xl font-bold shadow-md">
        🛍️ Shopping Assistant Chatbot
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="mb-4">
          <p className="text-sm text-gray-600 mb-2">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {["blue denim jacket", "summer dresses", "leather jacket", "affordable shirts", "red winter coat"].map((example, idx) => (
              <button
                key={idx}
                className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm hover:bg-blue-200 transition"
                onClick={() => handleExampleClick(example)}
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        {messages.map((msg, index) => (
          <div
            key={index}
            className={`my-3 flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-2xl px-4 py-3 rounded-2xl break-words shadow-sm ${
                msg.role === "user"
                  ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-br-none"
                  : "bg-white text-gray-800 border border-gray-200 rounded-bl-none"
              }`}
            >
              {msg.role === "system" && "🤖 "}
              {msg.role === "assistant" && "🛍️ "}
              {msg.content}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start my-3">
            <div className="bg-white border border-gray-200 px-4 py-3 rounded-2xl rounded-bl-none">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }}></div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={bottomRef} />
      </div>

      <div className="p-4 bg-white border-t border-gray-200">
        <div className="flex items-center">
          <textarea
            className="flex-1 border border-gray-300 rounded-l-xl px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={1}
            placeholder="Type your message (e.g., 'I want a blue denim jacket')..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
          />
          <button
            className={`bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-3 rounded-r-xl hover:from-blue-700 hover:to-purple-700 transition ${
              isLoading ? "opacity-50 cursor-not-allowed" : ""
            }`}
            onClick={handleSend}
            disabled={isLoading}
          >
            {isLoading ? "..." : "Send"}
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2 text-center">
          Powered by AI Product Search • Backend running on port 8000
        </p>
      </div>
    </div>
  );
}