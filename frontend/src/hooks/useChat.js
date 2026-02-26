import { useState } from 'react'
import { sendMessageToAPI } from '../api/chat'
import { getAccessToken } from '../utils/storage'

export default function useChat(user, onPlaceOrder) {
  const [messages, setMessages] = useState([])

  const sendMessage = async (text) => {
    setMessages(prev => [...prev, { role: 'user', text }])

    try {
      const token = getAccessToken()
      const data = await sendMessageToAPI(text, token)

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
      ])

      // ❌ Auto‑order disabled – user must click "Buy Now"
      // if (data.products && data.products.length > 0) {
      //   const buyMatch = text.match(/\b(buy|purchase|order)\s+(.+)/i);
      //   if (buyMatch) {
      //     const productQuery = buyMatch[2].trim().toLowerCase();
      //     const matchedProduct = data.products.find(p =>
      //       p.name.toLowerCase().includes(productQuery) ||
      //       productQuery.includes(p.name.toLowerCase())
      //     );
      //     if (matchedProduct && user) {
      //       onPlaceOrder(matchedProduct.name, {
      //         name: user.name || '',
      //         email: user.email,
      //         password: '',
      //         phone: user.phone || '',
      //         address: user.address || ''
      //       });
      //     }
      //   }
      // }
    } catch (error) {
      console.error('Error sending message:', error)
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: 'Sorry, I encountered an error. Please try again.',
          intent_badge: { intent: 'error', confidence: 0, level: 'low' },
        },
      ])
    }
  }

  return { messages, sendMessage, isEmpty: messages.length === 0 }
}