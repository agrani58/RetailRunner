// frontend/src/hooks/useAuth.js
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from 'react';
import {
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  setAccessToken,
  setRefreshToken,
  setStoredUser,
  clearStorage,
  refreshToken as doRefreshToken,
  isTokenExpired,
} from '../utils/storage';
import { clearMessages } from '../utils/chatCache';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user,             setUser]             = useState(null);
  const [isAuthenticated,  setIsAuthenticated]  = useState(false);
  const [loading,          setLoading]          = useState(true);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const refreshTimerRef = useRef(null);

  // ── Proactive token refresh ─────────────────────────────────────────
  const scheduleRefresh = useCallback((accessToken) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    try {
      const payload = JSON.parse(atob(accessToken.split('.')[1]));
      const expiresIn = payload.exp * 1000 - Date.now();
      const delay = Math.max(expiresIn - 60_000, 5_000);
      refreshTimerRef.current = setTimeout(async () => {
        try {
          const newToken = await doRefreshToken();
          if (newToken) scheduleRefresh(newToken);
        } catch {
          // silent
        }
      }, delay);
    } catch {
      // ignore
    }
  }, []);

  // ── Restore session on mount ────────────────────────────────────────
  useEffect(() => {
    const restore = async () => {
      const storedToken = getAccessToken();
      const storedUser  = getStoredUser();

      if (!storedToken || !storedUser) {
        setLoading(false);
        return;
      }

      if (!isTokenExpired(storedToken)) {
        setUser(storedUser);
        setIsAuthenticated(true);
        scheduleRefresh(storedToken);
        setLoading(false);
        return;
      }

      const rt = getRefreshToken();
      if (!rt) {
        clearStorage();
        setLoading(false);
        return;
      }

      try {
        const newToken = await doRefreshToken();
        if (newToken) {
          setUser(storedUser);
          setIsAuthenticated(true);
          scheduleRefresh(newToken);
        } else {
          clearStorage();
        }
      } catch {
        clearStorage();
      } finally {
        setLoading(false);
      }
    };

    restore();

    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, [scheduleRefresh]);

  // ── Login ───────────────────────────────────────────────────────────
  const login = useCallback(async (email, password) => {
    try {
      const response = await fetch(`${API_URL}/login`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        return { success: false, error: err.detail || 'Invalid email or password' };
      }

      const data = await response.json();
      const { access_token, refresh_token, user_data } = data;

      setAccessToken(access_token);
      if (refresh_token) setRefreshToken(refresh_token);

      const existing = getStoredUser() || {};
      const userData = {
        id:         user_data?.id        ?? user_data?.user_id,
        email:      user_data?.email     ?? email,
        name:       existing.name        || user_data?.name        || '',
        phone:      existing.phone       || user_data?.phone       || '',
        address:    existing.address     || user_data?.address     || '',
        city:       existing.city        || user_data?.city        || '',
        postalCode: existing.postalCode  || user_data?.postalCode  || '',
        country:    existing.country     || user_data?.country     || '',
      };

      setStoredUser(userData);
      setUser(userData);
      setIsAuthenticated(true);
      scheduleRefresh(access_token);
      localStorage.setItem('last_used_email', email);

      const profileComplete = !!(userData.name && userData.phone && userData.address);
      if (!profileComplete) setShowProfileModal(true);

      return { success: true, user: userData };
    } catch (err) {
      return { success: false, error: err.message || 'Login failed' };
    }
  }, [scheduleRefresh]);

  // ── Logout ──────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);

    const currentUserId = getStoredUser()?.id;
    console.log('useAuth: logout called, currentUserId =', currentUserId);

    const rt = getRefreshToken();
    const at = getAccessToken();

    if (rt && at) {
      try {
        await fetch(`${API_URL}/logout`, {
          method:  'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${at}`,
          },
          body: JSON.stringify({ refresh_token: rt }),
        });
      } catch { /* ignore */ }
    }

    clearStorage();
    setUser(null);
    setIsAuthenticated(false);
    setShowProfileModal(false);

    // Clear chat message cache for this user
    if (currentUserId != null) {
      console.log('useAuth: clearing messages for user', currentUserId);
      clearMessages(currentUserId);
    } else {
      console.log('useAuth: currentUserId is null, not clearing chat cache');
    }
  }, []);

  // ── updateUser — merge any fields into user state ───────────────────
  const updateUser = useCallback((updates) => {
    setUser((prev) => {
      const updated = { ...prev, ...updates };
      setStoredUser(updated);
      return updated;
    });
  }, []);

  // ── updateProfile — used by MandatoryProfileModal & ProfilePage ─────
  const updateProfile = useCallback((profileData) => {
    setUser((prev) => {
      const updated = { ...prev, ...profileData };
      setStoredUser(updated);
      return updated;
    });
    setShowProfileModal(false);
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated,
      loading,
      showProfileModal,
      setShowProfileModal,
      login,
      logout,
      updateUser,
      updateProfile,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

export default useAuth;