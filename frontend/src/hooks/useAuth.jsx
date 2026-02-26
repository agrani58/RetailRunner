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
  const [showProfileModal, setShowProfileModal] = useState(false); // <-- new
  const navigate = useNavigate();

  // Helper to load profile from localStorage for a given email
  const loadProfile = (email) => {
    if (!email) return {};
    const saved = localStorage.getItem(`user_profile_${email}`);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.error("Failed to parse profile", e);
      }
    }
    return {};
  };

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

  // Merge user data with profile from localStorage
  const mergeWithProfile = (userData) => {
    if (!userData || !userData.email) return userData;
    const profile = loadProfile(userData.email);
    return { ...userData, ...profile };
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
        const mergedUser = mergeWithProfile(userData);
        setUserState(mergedUser);
        setUser(mergedUser);
      } catch {
        try {
          const refreshData = await refreshAccessToken(refreshToken);
          const { access_token, refresh_token, user_data } = refreshData;
          setTokens(access_token, refresh_token);
          const mergedUser = mergeWithProfile(user_data);
          setUser(mergedUser);
          setUserState(mergedUser);
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

  // ✅ Login with mandatory profile check
  const login = async (email, password, rememberMe) => {
    try {
      const data = await apiLogin(email, password);
      const { access_token, refresh_token, user_data } = data;

      const mergedUser = mergeWithProfile(user_data);

      setTokens(access_token, refresh_token);
      setUser(mergedUser);
      setUserState(mergedUser);

      if (rememberMe) localStorage.setItem("last_used_email", email);
      else localStorage.removeItem("last_used_email");

      navigate("/");

      // If profile does not exist, force the modal
      if (!profileExists(user_data.email)) {
        setShowProfileModal(true);
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
    setShowProfileModal(false); // close modal on logout
    navigate("/login");
  };

  // ✅ Update profile and close modal
  const updateProfile = (profileData) => {
    const updatedUser = { ...user, ...profileData };
    setUserState(updatedUser);
    setUser(updatedUser);
    if (user?.email) {
      localStorage.setItem(`user_profile_${user.email}`, JSON.stringify(profileData));
    }
    // Close the mandatory modal if it was open
    setShowProfileModal(false);
  };

  const value = {
    user,
    login,
    signup,
    logout,
    updateProfile,
    isAuthenticated: !!user,
    loading,
    showProfileModal,      // <-- expose
    setShowProfileModal,   // <-- expose (optional, for manual close after save)
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};