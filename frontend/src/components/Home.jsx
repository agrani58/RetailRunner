import React from "react";
import useChat from "../hooks/useChat";
import Landing from "./Landing";
import Chat from "./Chat";

export default function Home() {
  const { messages, sendMessage, isEmpty } = useChat();

  return isEmpty ? (
    <Landing onSend={sendMessage} />
  ) : (
    <Chat messages={messages} onSend={sendMessage} />
  );
}