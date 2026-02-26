import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import useTheme from "../hooks/useTheme";
import "../styles/Layout.css";

export default function AuthenticatedLayout() {
  const { theme, toggle } = useTheme();

  return (
    <div className="app" data-theme={theme}>
      <Sidebar toggleTheme={toggle} />
      <main className="chat-area">
        <div className="chat-container">
          <Outlet />
        </div>
      </main>
    </div>
  );
}