// hooks/useChat.js – updated
import { useState, useEffect } from 'react';
import { sendMessageToAPI } from '../api/chat';
import { getAccessToken } from '../utils/storage';
import { useWebSocket } from './useWebSockets';

export default function useChat(user, onPlaceOrder) {
  const [messages, setMessages] = useState([]);

  // WebSocket message handler
  const handleWsMessage = (data) => {
    if (data.type === 'order_confirmation') {
      // Add order confirmation without badge
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: data.message,  // already contains ✅
        }
      ]);
    } else if (data.type === 'bot_status') {
      // Status updates from the order bot
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: data.message,
        }
      ]);
    }
  };

  const { isConnected } = useWebSocket(handleWsMessage);

  useEffect(() => {
    console.log('WebSocket connected:', isConnected);
  }, [isConnected]);

  const sendMessage = async (text) => {
    setMessages(prev => [...prev, { role: 'user', text }]);

    try {
      const token = getAccessToken();
      const data = await sendMessageToAPI(text, token);

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: data.response,
          intent_badge: {
            intent: data.intent_label,
            confidence: Math.round(data.intent_confidence * 100),
            level: data.intent_confidence > 0.7 ? 'high' : data.intent_confidence > 0.5 ? 'medium' : 'low',
          },
        },
        ...(data.products && data.products.length > 0
          ? [{ role: 'products', products: data.products }]
          : []),
      ]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: 'Sorry, I encountered an error. Please try again.',
          intent_badge: { intent: 'error', confidence: 0, level: 'low' },
        },
      ]);
    }
  };

  return { messages, sendMessage, isEmpty: messages.length === 0, isConnected };
}