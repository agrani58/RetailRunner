import { useState, useCallback, useEffect } from 'react'
import axios from 'axios'

const useChat = () => {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId] = useState(() => {
    let id = localStorage.getItem('chatSessionId')
    if (!id) {
      id = 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9)
      localStorage.setItem('chatSessionId', id)
    }
    return id
  })

  // Load messages from localStorage on mount
  useEffect(() => {
    const savedMessages = localStorage.getItem('chatMessages')
    if (savedMessages) {
      try {
        setMessages(JSON.parse(savedMessages))
      } catch (e) {
        console.error('Failed to parse saved messages:', e)
      }
    } else {
      // Add welcome message if no messages
      const welcomeMessage = {
        sender: 'bot',
        text: "Hello! I'm your AI shopping assistant. How can I help you today? You can ask me about products, prices, or get recommendations!",
        timestamp: new Date().toISOString(),
        products: []
      }
      setMessages([welcomeMessage])
    }
  }, [])

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('chatMessages', JSON.stringify(messages))
    }
  }, [messages])

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return

    // Add user message
    const userMessage = {
      sender: 'user',
      text: text,
      timestamp: new Date().toISOString(),
    }
    
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setIsLoading(true)

    try {
      // Handle greetings
      const lowerText = text.toLowerCase().trim()
      const greetings = ['hi', 'hello', 'hey', 'greetings', 'how are you']
      
      if (greetings.some(greet => lowerText.includes(greet))) {
        setTimeout(() => {
          const botMessage = {
            sender: 'bot',
            text: "Hello! 👋 I'm here to help you with your shopping needs. What are you looking for today?",
            timestamp: new Date().toISOString(),
            products: []
          }
          setMessages([...updatedMessages, botMessage])
          setIsLoading(false)
        }, 500)
        return
      }

      // Send to backend
      const response = await axios.post('http://localhost:8000/chat', {
        query: text
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
        // Removed strict timeout
      })

      const botMessage = {
        sender: 'bot',
        text: response.data.response,
        products: response.data.products || [],
        timestamp: new Date().toISOString(),
      }
      
      setMessages([...updatedMessages, botMessage])
      
    } catch (error) {
      console.error('Error sending message:', error)
      
      let errorMessage
      if (error.code === 'ECONNABORTED') {
        errorMessage = {
          sender: 'bot',
          text: "The search is taking a bit longer. Please wait or try a different query.",
          timestamp: new Date().toISOString(),
          products: []
        }
      } else {
        errorMessage = {
          sender: 'bot',
          text: "I apologize, but I'm having trouble connecting. Please try again in a moment.",
          timestamp: new Date().toISOString(),
          products: []
        }
      }
      
      setMessages([...updatedMessages, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }, [messages])

  const clearMessages = useCallback(() => {
    const welcomeMessage = {
      sender: 'bot',
      text: "Chat cleared! I'm ready to help you with your shopping needs. What would you like to find today?",
      timestamp: new Date().toISOString(),
      products: []
    }
    setMessages([welcomeMessage])
    localStorage.setItem('chatMessages', JSON.stringify([welcomeMessage]))
  }, [])

  return {
    messages,
    isLoading,
    sendMessage,
    clearMessages,
    sessionId
  }
}

export default useChat