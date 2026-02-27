// hooks/useChat.js
// WebSocket is used ONLY for order bot status messages in the chat UI.
// All authentication is HTTP-only (handled by useAuth.js).

import { useState, useCallback } from 'react';
import { sendMessageToAPI } from '../api/chat';
import { getAccessToken } from '../utils/storage';
import useWebSocketHook from './useWebSockets';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function useChat(user, onPlaceOrder, initialMessages = []) {
  const [messages, setMessages] = useState(initialMessages);
  // Track whether the bot is waiting for user to confirm payment
  const [awaitingPaymentConfirm, setAwaitingPaymentConfirm] = useState(false);

  // ── WebSocket handler — bot status logs only ─────────────────────────
  const handleWsMessage = useCallback((data) => {
    if (!data?.type) return;

    if (data.type === 'bot_status') {
      setMessages((prev) => [
        ...prev,
        { role: 'bot_status', text: data.message },
      ]);

      // Bot is asking the user to fill in address + payment
      if (
        data.message?.toLowerCase().includes('shipping address') ||
        data.message?.toLowerCase().includes('fill in your') ||
        data.message?.toLowerCase().includes('payment')
      ) {
        setAwaitingPaymentConfirm(true);
      }

      // Bot finished — clear the confirm state
      if (
        data.message?.toLowerCase().includes('order placed') ||
        data.message?.toLowerCase().includes('successfully') ||
        data.message?.toLowerCase().includes('error') ||
        data.message?.toLowerCase().includes('failed')
      ) {
        setAwaitingPaymentConfirm(false);
      }
    }

    if (data.type === 'order_confirmation') {
      setMessages((prev) => [
        ...prev,
        { role: 'order_confirmation', text: data.message },
      ]);
      setAwaitingPaymentConfirm(false);
    }

    // Bot explicitly asking for payment confirmation
    if (data.type === 'await_payment_confirm') {
      setAwaitingPaymentConfirm(true);
      setMessages((prev) => [
        ...prev,
        { role: 'bot_status', text: data.message, awaitPayment: true },
      ]);
    }
  }, []);

  const { isConnected, sendMessage: wsSend } = useWebSocketHook(handleWsMessage);

  // ── Send payment confirmed signal to backend via WS ──────────────────
  const confirmPayment = useCallback(() => {
    wsSend({ type: 'payment_confirmed' });
    setAwaitingPaymentConfirm(false);
    setMessages((prev) => [
      ...prev,
      { role: 'user', text: '✅ Payment confirmed — completing order…' },
    ]);
  }, [wsSend]);

  // ── Chat message send (HTTP) ─────────────────────────────────────────
  const sendMessage = useCallback(async (text) => {
    setMessages((prev) => [...prev, { role: 'user', text }]);

    try {
      const token = getAccessToken();
      const data  = await sendMessageToAPI(text, token);

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.response,
          intent_badge: {
            intent:     data.intent_label,
            confidence: Math.round(data.intent_confidence * 100),
            level:
              data.intent_confidence > 0.7 ? 'high'
              : data.intent_confidence > 0.5 ? 'medium'
              : 'low',
          },
        },
        ...(data.products?.length > 0
          ? [{ role: 'products', products: data.products }]
          : []),
      ]);
    } catch (error) {
      console.error('Chat error:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: 'Sorry, I encountered an error. Please try again.',
        },
      ]);
    }
  }, []);

  return {
    messages,
    sendMessage,
    isEmpty: messages.length === 0,
    isConnected,
    awaitingPaymentConfirm,
    confirmPayment,
  };
}