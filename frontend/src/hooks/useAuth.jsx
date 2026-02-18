import { useState, useEffect, useContext, createContext } from "react";
import { useNavigate } from "react-router-dom";
import {
  login as apiLogin,
  signup as apiSignup,
  logout as apiLogout,
  refreshAccessToken,
  getCurrentUser,
} from "../api/auth";
import {
  setTokens,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setUser,
  getUser,
  clearUser,
} from "../utils/storage";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUserState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState({ message: "", visible: false });
  const navigate = useNavigate();

  // Helper to check if profile exists for current user
  const profileExists = (email) => {
    if (!email) return false;
    const saved = localStorage.getItem(`user_profile_${email}`);
    if (!saved) return false;
    try {
      JSON.parse(saved);
      return true;
    } catch {
      return false;
    }
  };

  // Restore session on app start
  useEffect(() => {
    const restoreSession = async () => {
      const accessToken = getAccessToken();
      const refreshToken = getRefreshToken();
      const storedUser = getUser();

      if (!accessToken || !refreshToken || !storedUser) {
        setLoading(false);
        return;
      }

      try {
        const userData = await getCurrentUser(accessToken);
        setUserState(userData);
        setUser(userData);
      } catch {
        try {
          const refreshData = await refreshAccessToken(refreshToken);
          const { access_token, refresh_token, user_data } = refreshData;
          setTokens(access_token, refresh_token);
          setUser(user_data);
          setUserState(user_data);
        } catch {
          clearTokens();
          clearUser();
          setUserState(null);
        }
      }

      setLoading(false);
    };

    restoreSession();
  }, []);

  // ✅ Login with toast logic
  const login = async (email, password, rememberMe) => {
    try {
      const data = await apiLogin(email, password);
      const { access_token, refresh_token, user_data } = data;

      setTokens(access_token, refresh_token);
      setUser(user_data);
      setUserState(user_data);

      if (rememberMe) localStorage.setItem("last_used_email", email);
      else localStorage.removeItem("last_used_email");

      navigate("/");

      // Show toast only if profile not exists
      if (!profileExists(user_data.email)) {
        setToast({
          message: "Would you like to complete your profile now?",
          visible: true,
        });
      }

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || "Login failed",
      };
    }
  };

  const signup = async (email, password) => {
    try {
      await apiSignup(email, password);
      navigate("/login", { state: { email } });
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || "Signup failed" };
    }
  };

  const logout = async () => {
    const accessToken = getAccessToken();
    const refreshToken = getRefreshToken();
    try {
      if (refreshToken && accessToken) await apiLogout(refreshToken, accessToken);
    } catch (e) {
      console.error("Logout API error", e);
    }

    clearTokens();
    clearUser();
    setUserState(null);
    navigate("/login"); // ✅ logout redirect
  };

  const hideToast = () => setToast({ message: "", visible: false });

  const value = {
    user,
    login,
    signup,
    logout,
    isAuthenticated: !!user,
    loading,
    toast,
    hideToast,
    setToast,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
