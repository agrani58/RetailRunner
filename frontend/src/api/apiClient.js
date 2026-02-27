// src/api/apiClient.js
// Shared axios instance used by orders.js, wishlist.js, etc.
// Automatically refreshes the access token on 401 and retries once.

import axios from 'axios';
import {
  getAccessToken,
  setAccessToken,
  setRefreshToken,
  getRefreshToken,
  clearStorage,
} from '../utils/storage';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({ baseURL: API_URL });

// ── Request interceptor: attach current access token ────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Response interceptor: refresh token on 401, retry once ──────────────────
let isRefreshing = false;
let pendingQueue = []; // requests waiting for the new token

function processQueue(error, token = null) {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token);
  });
  pendingQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Only handle 401, and only retry once
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      // Queue this request until the ongoing refresh completes
      return new Promise((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return apiClient(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    const rt = getRefreshToken();
    if (!rt) {
      clearStorage();
      window.location.href = '/login';
      return Promise.reject(error);
    }

    try {
      const response = await axios.post(`${API_URL}/refresh`, {
        refresh_token: rt,
      });

      const { access_token, refresh_token } = response.data;
      setAccessToken(access_token);
      if (refresh_token) setRefreshToken(refresh_token);

      processQueue(null, access_token);
      originalRequest.headers.Authorization = `Bearer ${access_token}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      clearStorage();
      window.location.href = '/login';
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export default apiClient;