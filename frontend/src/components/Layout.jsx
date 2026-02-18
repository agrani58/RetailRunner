import React from "react";
import Sidebar from "./Sidebar";
import Chat from "./Chat";
import Landing from "./Landing";
import useChat from "../hooks/useChat";
import useTheme from "../hooks/useTheme";
import "../styles/layout.css";

export default function Layout() {
  const { messages, sendMessage, isEmpty } = useChat();
  const { toggle, theme } = useTheme();

  return (
    <div className="app" data-theme={theme}>
      <div className="gradient-background">
        {Array.from({ length: 5 }).map((_, i) => {
          const size = [600, 500, 400, 450, 650][i];
          const positions = [
            { top: "-200px", right: "-150px" },
            { bottom: "-150px", left: "-100px" },
            { top: "40%", left: "60%" },
            { bottom: "30%", right: "60%" },
            { top: "60%", left: "10%" }
          ][i];
          
          const gradientColors = theme === "dark"
            ? {
                1: "rgba(217, 154, 91, 0.25)",
                2: "rgba(38, 35, 31, 0.25)",
                3: "rgba(154, 160, 107, 0.25)",
                4: "rgba(51, 47, 43, 0.25)",
              }
            : {
                1: "rgba(170, 174, 127, 0.45)",
                2: "rgba(208, 214, 179, 0.50)",
                3: "rgba(244, 179, 107, 0.40)",
                4: "rgba(200, 185, 150, 0.40)",
              };
          
          const color = gradientColors[(i % 4) + 1];
          
          return (
            <div
              key={i}
              className="gradient-circle"
              style={{
                width: `${size}px`,
                height: `${size}px`,
                background: `radial-gradient(circle, ${color}, transparent 70%)`,
                filter: "blur(60px)",
                opacity: 0.7,
                borderRadius: "50%",
                position: "absolute",
                animation: `float ${20 + i * 5}s infinite ease-in-out`,
                animationDelay: `${-i * 5}s`,
                ...positions
              }}
            />
          );
        })}
      </div>
      
      <Sidebar toggleTheme={toggle} />
      <main className="chat-area">
        <div className="chat-container">
          {isEmpty ? (
            <Landing onSend={sendMessage} />
          ) : (
            <Chat messages={messages} onSend={sendMessage} />
          )}
        </div>
      </main>
    </div>
  );
}