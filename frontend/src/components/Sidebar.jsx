import React from 'react'
import { FiMessageSquare, FiTrash2, FiClock, FiCheckCircle } from 'react-icons/fi'
import { AiOutlineRobot } from 'react-icons/ai'
import './Sidebar.css'

const Sidebar = ({ isOpen, onClose, activeView, setActiveView }) => {
  if (!isOpen) return null

  const clearChat = () => {
    if (window.confirm('Are you sure you want to clear the chat?')) {
      localStorage.removeItem('chatMessages')
      window.location.reload()
    }
  }

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="logo-container">
          <AiOutlineRobot className="logo-icon" />
          <span className="logo-text">AI Shopping Assistant</span>
        </div>
      </div>

      <div className="sidebar-content">
        <nav className="nav-menu">
          <div className="nav-section">
            <p className="nav-label">CHAT</p>
            <button 
              className={`nav-item ${activeView === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveView('chat')}
            >
              <FiMessageSquare className="nav-icon" />
              <span>New Chat</span>
            </button>
            
            <button 
              className="nav-item"
              onClick={clearChat}
            >
              <FiTrash2 className="nav-icon" />
              <span>Clear Chat</span>
            </button>

            <button 
              className={`nav-item ${activeView === 'history' ? 'active' : ''}`}
              onClick={() => setActiveView('history')}
            >
              <FiClock className="nav-icon" />
              <span>Chat History</span>
            </button>
          </div>

          <div className="nav-section">
            <p className="nav-label">CAPABILITIES</p>
            <div className="capabilities-list">
              <div className="capability-item">
                <FiCheckCircle className="capability-icon" style={{color: '#10a37f'}} />
                <span className="capability-text">User & Bot messages distinct</span>
              </div>
              <div className="capability-item">
                <FiCheckCircle className="capability-icon" style={{color: '#f59e0b'}} />
                <span className="capability-text">Messages persist per session</span>
              </div>
              <div className="capability-item">
                <FiCheckCircle className="capability-icon" style={{color: '#3b82f6'}} />
                <span className="capability-text">Handles greetings & small talk</span>
              </div>
              <div className="capability-item">
                <FiCheckCircle className="capability-icon" style={{color: '#8b5cf6'}} />
                <span className="capability-text">Detects shopping intent</span>
              </div>
              <div className="capability-item">
                <FiCheckCircle className="capability-icon" style={{color: '#10b981'}} />
                <span className="capability-text">Responds within 2 seconds</span>
              </div>
              <div className="capability-item">
                <FiCheckCircle className="capability-icon" style={{color: '#f97316'}} />
                <span className="capability-text">Chat history reloads correctly</span>
              </div>
            </div>
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="status-info">
            <div className="status-indicator online"></div>
            <div className="status-text">
              <p className="status-title">System Status</p>
              <p className="status-subtitle">All systems operational</p>
            </div>
          </div>
          <div className="session-info">
            <p>Session: <span className="session-id">Guest-{Math.random().toString(36).substr(2, 6)}</span></p>
            <p className="session-time">Started: {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Sidebar