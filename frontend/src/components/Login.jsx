import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import '../styles/Login.css';

export default function Login() {
  const [email,      setEmail]      = useState('');
  const [password,   setPassword]   = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [error,      setError]      = useState('');
  const [loading,    setLoading]    = useState(false);

  const { login }  = useAuth();
  const navigate   = useNavigate();
  const location   = useLocation();

  useEffect(() => {
    // Pre-fill email if coming from signup or from localStorage
    if (location.state?.email) {
      setEmail(location.state.email);
    } else {
      const lastEmail = localStorage.getItem('last_used_email');
      if (lastEmail) setEmail(lastEmail);
    }
  }, [location.state]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await login(email, password);

    setLoading(false);

    if (!result.success) {
      setError(result.error || 'Invalid email or password');
    } else {
      navigate('/');
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="brand">Welcome back</h1>

        <form onSubmit={handleSubmit} className="auth-form" autoComplete="on">
          <input
            type="email"
            name="email"
            autoComplete="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="auth-input"
          />
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="auth-input"
          />

          <div className="remember-me">
            <label>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              />
              <span>Remember me</span>
            </label>
          </div>

          {error && <div className="auth-error-plain">{error}</div>}

          <button type="submit" disabled={loading} className="auth-button">
            {loading ? 'Logging in…' : 'Log in'}
          </button>
        </form>

        <p className="auth-switch">
          Don't have an account? <Link to="/signup">Sign up</Link>
        </p>
      </div>
    </div>
  );
}