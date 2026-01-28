import React, { useState, useRef, useEffect } from 'react'
import { FiSend, FiShoppingCart, FiPackage, FiChevronRight, FiClock, FiUser } from 'react-icons/fi'
import { AiOutlineRobot } from 'react-icons/ai'
import Message from './Message'
import ProductCard from './ProductCard'
import useChat from '../hooks/useChat'
import './ChatInterface.css'

const ChatInterface = () => {
  const [input, setInput] = useState('')
  const [typingIndicator, setTypingIndicator] = useState(false)
  const messagesEndRef = useRef(null)
  const { messages, isLoading, sendMessage, clearMessages, sessionId } = useChat()
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    
    setTypingIndicator(true)
    await sendMessage(input)
    setInput('')
    setTypingIndicator(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const sampleQueries = [
    "Hi there!",
    "How are you today?",
    "Find me running shoes under $100",
    "Show me blue jeans for men",
    "I need a winter jacket",
    "What's on sale?",
    "Recommend comfortable t-shirts",
    "Looking for leather boots"
  ]

  const lastMessage = messages[messages.length - 1]
  
  const getResponseTime = () => {
    if (messages.length < 2) return null
    const lastUserMessage = messages[messages.length - 2]
    const lastBotMessage = messages[messages.length - 1]
    
    if (lastUserMessage.sender === 'user' && lastBotMessage.sender === 'bot') {
      const userTime = new Date(lastUserMessage.timestamp)
      const botTime = new Date(lastBotMessage.timestamp)
      return Math.round((botTime - userTime) / 100) / 10
    }
    return null
  }

  const responseTime = getResponseTime()

  return (
    <div className="chat-interface">
      {/* Session Info Bar */}
      <div className="session-bar">
        <div className="session-info">
          <FiClock className="session-icon" />
          <span className="session-text">Session: <strong>{sessionId ? sessionId.substring(0, 12) : 'Loading...'}</strong></span>
          <span className="message-count">{messages.length} messages</span>
        </div>
        <div className="performance-info">
          {responseTime && (
            <span className="response-time">
              Last response: <strong>{responseTime}s</strong>
            </span>
          )}
          <span className="performance-status">
            <span className="status-dot"></span>
            Performance: Good
          </span>
        </div>
      </div>

      {/* Chat Messages Area */}
      <div className="messages-area">
        {messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-header">
              <div className="robot-icon-container">
                <AiOutlineRobot className="robot-icon" />
              </div>
              <h2>AI Shopping Assistant</h2>
              <p className="welcome-subtitle">I can help you find products, compare prices, and get recommendations!</p>
              
              <div className="capabilities">
                <div className="capability">
                  <FiUser className="capability-icon user" />
                  <span>User messages shown in blue</span>
                </div>
                <div className="capability">
                  <AiOutlineRobot className="capability-icon bot" />
                  <span>Bot messages shown in green</span>
                </div>
                <div className="capability">
                  <FiClock className="capability-icon" />
                  <span>Messages persist per session</span>
                </div>
              </div>
            </div>
            
            <div className="sample-queries">
              <h3 className="sample-title">Try asking me:</h3>
              {sampleQueries.map((query, index) => (
                <button
                  key={index}
                  onClick={() => sendMessage(query)}
                  className="query-button"
                >
                  <FiChevronRight className="query-icon" />
                  <span>{query}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {/* Messages list */}
            {messages.map((message, index) => (
              <Message key={index} message={message} />
            ))}

            {/* Typing indicator */}
            {typingIndicator && (
              <div className="typing-indicator">
                <div className="typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span className="typing-text">Assistant is typing...</span>
              </div>
            )}

            {/* Loading indicator */}
            {isLoading && (
              <div className="loading-message">
                <div className="avatar">
                  <div className="avatar-icon">
                    <AiOutlineRobot />
                  </div>
                </div>
                <div className="loading-content">
                  <div className="loading-line short"></div>
                  <div className="loading-line medium"></div>
                  <div className="loading-line short"></div>
                </div>
              </div>
            )}

            {/* Products from last response */}
            {lastMessage?.products && lastMessage.products.length > 0 && (
              <div className="products-section">
                <div className="products-header">
                  <FiPackage className="products-icon" />
                  <h3>Found Products</h3>
                  <span className="products-count">{lastMessage.products.length} items</span>
                  {responseTime && (
                    <span className="response-time-badge">
                      Response time: {responseTime}s
                    </span>
                  )}
                </div>
                <div className="products-grid">
                  {lastMessage.products.slice(0, 3).map((product, index) => (
                    <ProductCard key={index} product={product} />
                  ))}
                </div>
                {lastMessage.products.length > 3 && (
                  <p className="more-products">
                    ... and {lastMessage.products.length - 3} more products
                  </p>
                )}
              </div>
            )}
          </>
        )}

        <div ref={messagesEndRef} className="scroll-anchor" />
      </div>

      {/* Input Area */}
      <div className="input-area">
        <form onSubmit={handleSubmit} className="input-form">
          <div className="input-container">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message AI Shopping Assistant..."
              className="message-input"
              rows="1"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="send-button"
            >
              <FiSend />
            </button>
          </div>
          
          <div className="input-footer">
            <div className="footer-left">
              <button
                type="button"
                onClick={clearMessages}
                className="clear-button"
              >
                Clear chat
              </button>
              <span className="hint">Press Enter to send • Shift+Enter for new line</span>
            </div>
            <div className="footer-right">
              <FiShoppingCart className="cart-icon" />
              <span>Powered by FastAPI & Urban Threads</span>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

export default ChatInterface