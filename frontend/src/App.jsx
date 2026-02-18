import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Login from './components/Login'
import Signup from './components/Signup'
import AuthenticatedLayout from './components/AuthenticatedLayout'
import Home from './components/Home'
import ProfilePage from './components/ProfilePage'
import Toast from './components/Toast'

function App() {
  const { isAuthenticated, loading, toast, hideToast } = useAuth()

  if (loading) return null

  const ProtectedRoute = ({ children }) => {
    return isAuthenticated ? children : <Navigate to="/login" replace />
  }

  return (
    <>
      {toast.visible && (
        <Toast
          message={toast.message}
          onConfirm={hideToast}
          onDismiss={hideToast}
        />
      )}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AuthenticatedLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Home />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </>
  )
}

export default App