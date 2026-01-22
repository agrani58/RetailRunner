// frontend/src/app.jsx
import React from "react";
import ChatInterface from "./ChatInterface";

async function sendMessageToBackend(message) {
  try {
    // Changed from localhost:5000 to localhost:8000 to match backend
    const res = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: message }),
    });
    
    if (!res.ok) {
      throw new Error(`Server error: ${res.status}`);
    }
    
    const data = await res.json();
    return data.response;
    
  } catch (error) {
    console.error("Error sending message:", error);
    return "I'm having trouble connecting to the server. Please make sure the backend is running on http://localhost:8000";
  }
}

export default function App() {
  return <ChatInterface sendMessage={sendMessageToBackend} />;
}