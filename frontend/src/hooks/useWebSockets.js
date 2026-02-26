// src/hooks/useWebSockets.js
import { useEffect, useRef, useState } from 'react';
import { getAccessToken, isTokenExpired, refreshToken } from '../utils/storage';

export function useWebSocket(onMessage) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 10;
  const baseDelay = 1000; // 1 second

  const connect = async () => {
    // Stop if we've exceeded max attempts
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      console.log('WebSocket: Max reconnection attempts reached, giving up.');
      return;
    }

    // Get a valid token (refresh if needed)
    let token = getAccessToken();
    if (!token) {
      console.log('WebSocket: No token, cannot connect.');
      return;
    }

    if (isTokenExpired(token)) {
      try {
        console.log('WebSocket: Token expired, refreshing...');
        const newTokens = await refreshToken();
        token = newTokens.access_token;
      } catch (error) {
        console.error('WebSocket: Token refresh failed, cannot connect.', error);
        return;
      }
    }

    const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      reconnectAttemptsRef.current = 0; // reset on successful connection
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch (err) {
        console.error('Failed to parse WebSocket message', err);
      }
    };

    ws.onclose = (event) => {
      console.log(`WebSocket disconnected (code ${event.code}), reconnecting...`);
      setIsConnected(false);
      wsRef.current = null;

      // If closed abnormally (not 1000 = normal), attempt reconnect
      if (event.code !== 1000) {
        const delay = baseDelay * Math.pow(2, reconnectAttemptsRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttemptsRef.current += 1;
          connect();
        }, delay);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error', error);
      ws.close(); // will trigger onclose
    };
  };

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close(1000, 'Component unmount');
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, []);

  return { isConnected };
}