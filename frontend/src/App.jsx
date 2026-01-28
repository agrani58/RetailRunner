import React, { useState } from 'react'
import { FiMessageSquare } from 'react-icons/fi'
import { AiOutlineRobot } from 'react-icons/ai'
import ChatInterface from './components/ChatInterface'
import Sidebar from './components/Sidebar'
import './App.css'

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [activeView, setActiveView] = useState('chat')

  return (
    <div className="app-container">
      {/* Sidebar */}
      <Sidebar 
        isOpen={isSidebarOpen} 
        onClose={() => setIsSidebarOpen(false)}
        activeView={activeView}
        setActiveView={setActiveView}
      />

      {/* Main Content */}
      <div className="main-content" style={{ marginLeft: isSidebarOpen ? '280px' : '0' }}>
        {/* Top Navigation Bar */}
        <header className="header">
          <div className="header-left">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="sidebar-toggle"
            >
              <FiMessageSquare />
            </button>
            <div className="logo">
              <AiOutlineRobot className="logo-icon" />
              <h1>AI Shopping Assistant</h1>
            </div>
          </div>
          
          <div className="header-status">
            <span className="status-badge">
              <span className="status-dot"></span>
              Backend Connected
            </span>
          </div>
        </header>

        {/* Main Chat Area */}
        <main className="main-area">
          {activeView === 'chat' && <ChatInterface />}
          {activeView === 'history' && (
            <div className="history-view">
              <div className="history-container">
                <h2>Chat History</h2>
                <div className="history-list">
                  <p className="history-empty">
                    Chat history feature coming soon...
                  </p>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

export default App