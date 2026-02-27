// src/App.jsx
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import Login from './components/Login';
import Signup from './components/Signup';
import AuthenticatedLayout from './components/AuthenticatedLayout';
import Home from './components/Home';
import ProfilePage from './components/ProfilePage';
import OrdersPage from './components/OrdersPage';
import WishlistPage from './components/WishlistPage';
import MandatoryProfileModal from './components/MandatoryProfileModal';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function App() {
  const { loading, showProfileModal } = useAuth();

  // Don't render anything until we know auth state (avoids flicker/redirect)
  if (loading) return null;

  return (
    <>
      {showProfileModal && <MandatoryProfileModal />}
      <Routes>
        <Route path="/login"  element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AuthenticatedLayout />
            </ProtectedRoute>
          }
        >
          <Route index          element={<Home />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="orders"  element={<OrdersPage />} />
          <Route path="wishlist" element={<WishlistPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </>
  );
}

export default App;