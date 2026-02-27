// storage.js
// Centralised token + user storage.
// ALL fetch calls use VITE_API_URL so nothing is hardcoded to localhost.

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Keys ────────────────────────────────────────────────────────────────────
const ACCESS_TOKEN_KEY  = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY          = 'user';

// ── Access token ─────────────────────────────────────────────────────────────
export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token) {
  if (token) localStorage.setItem(ACCESS_TOKEN_KEY, token);
  else localStorage.removeItem(ACCESS_TOKEN_KEY);
}

// ── Refresh token ─────────────────────────────────────────────────────────────
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setRefreshToken(token) {
  if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
  else localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// ── User ─────────────────────────────────────────────────────────────────────
export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
}

// ── Full clear (logout) ───────────────────────────────────────────────────────
export function clearStorage() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// ── Token refresh ─────────────────────────────────────────────────────────────
// Uses VITE_API_URL — never hardcoded localhost.
// Returns the new access token string, or throws on failure.
export async function refreshToken() {
  const rt = getRefreshToken();
  if (!rt) throw new Error('No refresh token available');

  const response = await fetch(`${API_URL}/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: rt }),
  });

  if (!response.ok) {
    // Refresh failed (token expired/revoked) — clear everything
    clearStorage();
    throw new Error(`Refresh failed: ${response.status}`);
  }

  const data = await response.json();
  const newAccessToken  = data.access_token;
  const newRefreshToken = data.refresh_token;

  if (!newAccessToken) {
    clearStorage();
    throw new Error('Refresh response missing access_token');
  }

  setAccessToken(newAccessToken);
  if (newRefreshToken) setRefreshToken(newRefreshToken);

  return newAccessToken;
}

// ── JWT decode (no library needed) ───────────────────────────────────────────
export function decodeToken(token) {
  try {
    const payload = token.split('.')[1];
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
  } catch {
    return null;
  }
}

// Returns true if the token is expired or will expire within `bufferSeconds`
export function isTokenExpired(token, bufferSeconds = 30) {
  const decoded = decodeToken(token);
  if (!decoded?.exp) return true;
  return decoded.exp - bufferSeconds < Date.now() / 1000;
}

// ── Authenticated fetch wrapper ───────────────────────────────────────────────
// Automatically refreshes the token if it's about to expire, then retries.
export async function authFetch(url, options = {}) {
  let token = getAccessToken();

  // Proactively refresh if token is stale
  if (!token || isTokenExpired(token)) {
    try {
      token = await refreshToken();
    } catch (err) {
      // Refresh failed — clear auth and redirect to login
      clearStorage();
      window.location.href = '/login';
      throw err;
    }
  }

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
    Authorization: `Bearer ${token}`,
  };

  const res = await fetch(url, { ...options, headers });

  // If we still get 401 after refresh, force logout
  if (res.status === 401) {
    clearStorage();
    window.location.href = '/login';
    throw new Error('Session expired. Please log in again.');
  }

  return res;
}