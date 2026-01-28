import React from 'react'
import { AiOutlineRobot, AiOutlineUser } from 'react-icons/ai'
import { FiStar, FiPackage, FiDollarSign } from 'react-icons/fi'
import ReactMarkdown from 'react-markdown'
import './Message.css'

const Message = ({ message }) => {
  const isBot = message.sender === 'bot'

  return (
    <div className={`message ${isBot ? 'bot-message' : 'user-message'} fade-in`}>
      <div className="avatar">
        {isBot ? (
          <div className="avatar-icon bot-avatar">
            <AiOutlineRobot />
          </div>
        ) : (
          <div className="avatar-icon user-avatar">
            <AiOutlineUser />
          </div>
        )}
      </div>
      
      <div className="content">
        <div className="header">
          <span className="sender">{isBot ? 'Shopping Assistant' : 'You'}</span>
          <span className="timestamp">
            {new Date(message.timestamp).toLocaleTimeString([], { 
              hour: '2-digit', 
              minute: '2-digit' 
            })}
          </span>
        </div>
        
        <div className="text">
          <ReactMarkdown
            components={{
              p: ({ children }) => <p className="paragraph">{children}</p>,
              strong: ({ children }) => <strong className="bold">{children}</strong>,
              ul: ({ children }) => <ul className="list">{children}</ul>,
              li: ({ children }) => <li className="list-item">{children}</li>,
            }}
          >
            {message.text}
          </ReactMarkdown>
        </div>

        {/* Product highlights in bot messages */}
        {isBot && message.products && message.products.length > 0 && (
          <div className="product-highlights">
            <div className="highlights-header">
              <FiPackage className="highlights-icon" />
              <span className="highlights-title">Product Highlights</span>
            </div>
            <div className="highlights-grid">
              <div className="highlight-item">
                <FiStar className="star-icon" />
                <span>Top match: {Math.max(...message.products.map(p => p.match_percentage || 0))}%</span>
              </div>
              <div className="highlight-item">
                <FiDollarSign className="dollar-icon" />
                <span>From ${Math.min(...message.products.map(p => p.price || 0)).toFixed(2)}</span>
              </div>
              <div className="highlight-item">
                <span className="cart-emoji">🛒</span>
                <span>{message.products.length} products found</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Message