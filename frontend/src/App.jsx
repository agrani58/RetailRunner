import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Login from './components/Login'
import Signup from './components/Signup'
import AuthenticatedLayout from './components/AuthenticatedLayout'
import Home from './components/Home'
import ProfilePage from './components/ProfilePage'
import MandatoryProfileModal from './components/MandatoryProfileModal' // <-- new

function App() {
  const { isAuthenticated, loading, showProfileModal } = useAuth()

  if (loading) return null

  const ProtectedRoute = ({ children }) => {
    return isAuthenticated ? children : <Navigate to="/login" replace />
  }

  return (
    <>
      {/* Mandatory profile modal – shown when user needs to complete profile */}
      {showProfileModal && <MandatoryProfileModal />}

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