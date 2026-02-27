// useWebSockets.js
// WebSocket is used ONLY for order bot status logs in the chat interface.
// It NEVER clears auth storage or redirects on failure — auth is handled
// entirely by HTTP tokens in useAuth.js.

import { useEffect, useRef, useCallback, useState } from 'react';
import { getAccessToken, isTokenExpired } from '../utils/storage';

const WS_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws');

const INITIAL_DELAY = 2_000;
const MAX_DELAY     = 60_000;
const MAX_RETRIES   = 10;

function useWebSocketHook(onMessage) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef        = useRef(null);
  const retryTimer   = useRef(null);
  const retryCount   = useRef(0);
  const isMounted    = useRef(true);
  const onMessageRef = useRef(onMessage);

  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);

  const clearRetryTimer = () => {
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }
  };

  const closeSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen    = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror   = null;
      wsRef.current.onclose   = null;
      if (wsRef.current.readyState < WebSocket.CLOSING) {
        wsRef.current.close(1000, 'cleanup');
      }
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!isMounted.current) return;

    const token = getAccessToken();

    // If no token or token is expired, don't attempt WS — just retry later.
    // We do NOT clear storage or redirect. Auth is HTTP's responsibility.
    if (!token || isTokenExpired(token)) {
      retryCount.current += 1;
      if (retryCount.current <= MAX_RETRIES) {
        const delay = Math.min(INITIAL_DELAY * 2 ** retryCount.current, MAX_DELAY);
        retryTimer.current = setTimeout(connect, delay);
      }
      return;
    }

    closeSocket();

    let ws;
    try {
      ws = new WebSocket(`${WS_BASE}/ws?token=${token}`);
    } catch (err) {
      // WebSocket construction failed (bad URL etc.) — retry silently
      retryCount.current += 1;
      if (retryCount.current <= MAX_RETRIES) {
        const delay = Math.min(INITIAL_DELAY * 2 ** retryCount.current, MAX_DELAY);
        retryTimer.current = setTimeout(connect, delay);
      }
      return;
    }

    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMounted.current) { ws.close(); return; }
      setIsConnected(true);
      retryCount.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current?.(data);
      } catch {
        // Ignore malformed frames
      }
    };

    ws.onerror = () => {
      // Handled in onclose — no action needed here
    };

    ws.onclose = (event) => {
      if (!isMounted.current) return;
      setIsConnected(false);

      // Never clear storage, never redirect — just retry with backoff
      retryCount.current += 1;
      if (retryCount.current > MAX_RETRIES) return;

      const delay = Math.min(INITIAL_DELAY * 2 ** (retryCount.current - 1), MAX_DELAY);
      retryTimer.current = setTimeout(connect, delay);
    };
  }, [closeSocket]);

  useEffect(() => {
    isMounted.current = true;
    connect();
    return () => {
      isMounted.current = false;
      clearRetryTimer();
      closeSocket();
    };
  }, [connect, closeSocket]);

  const sendMessage = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { isConnected, sendMessage };
}

export const useWebSocket = useWebSocketHook;
export default useWebSocketHook;