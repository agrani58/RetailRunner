import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Configure axios
axios.defaults.baseURL = API_BASE_URL;
axios.defaults.headers.common['Content-Type'] = 'application/json';

// Request interceptor
axios.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      return Promise.reject(error);
    } else if (error.request) {
      console.error('Network error:', error.request);
      return Promise.reject(new Error('Network error. Please check your connection.'));
    } else {
      return Promise.reject(error);
    }
  }
);

const extractErrorMessage = (error) => {
  if (error.response && error.response.data) {
    const data = error.response.data;
    if (typeof data === 'string') return data;
    if (data.detail) {
      if (typeof data.detail === 'string') return data.detail;
      if (typeof data.detail === 'object') {
        if (Array.isArray(data.detail)) {
          return data.detail.map(err => err.msg || 'Validation error').join(', ');
        }
        return JSON.stringify(data.detail);
      }
    }
    if (data.message) return data.message;
    if (data.error) return data.error;
  }
  return error.message || 'An error occurred';
};

// User management - Store last used email SEPARATELY from form data
const getLastUsedEmail = () => {
  try {
    return localStorage.getItem('last_used_email');
  } catch (e) {
    console.error('Error getting last used email:', e);
    return null;
  }
};

const setLastUsedEmail = (email) => {
  try {
    localStorage.setItem('last_used_email', email);
  } catch (e) {
    console.error('Error saving last used email:', e);
  }
};

const getUserData = () => {
  try {
    const data = localStorage.getItem('user_data');
    return data ? JSON.parse(data) : null;
  } catch (e) {
    console.error('Error getting user data:', e);
    return null;
  }
};

const setUserData = (data) => {
  try {
    localStorage.setItem('user_data', JSON.stringify(data));
  } catch (e) {
    console.error('Error saving user data:', e);
  }
};

const clearUserData = () => {
  try {
    localStorage.removeItem('user_data');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  } catch (e) {
    console.error('Error clearing user data:', e);
  }
};

// Get initials for profile picture
const getInitials = (email) => {
  if (!email) return '?';
  const parts = email.split('@')[0];
  const nameParts = parts.split(/[._]/);
  if (nameParts.length >= 2) {
    return (nameParts[0][0] + nameParts[1][0]).toUpperCase();
  }
  return parts[0].toUpperCase();
};

// Profile Avatar Component
const ProfileAvatar = ({ email, size = 32 }) => {
  const initials = getInitials(email);
  const color = '#00a651'; // Always green
  
  return (
    <div 
      className="profile-avatar"
      style={{
        width: size,
        height: size,
        backgroundColor: color,
        color: 'white',
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size * 0.4,
        fontWeight: 'bold',
        marginRight: '10px'
      }}
    >
      {initials}
    </div>
  );
};

// Voice Icon SVG Component
const VoiceIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 15C13.6569 15 15 13.6569 15 12V6C15 4.34315 13.6569 3 12 3C10.3431 3 9 4.34315 9 6V12C9 13.6569 10.3431 15 12 15Z" 
          stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M19 12V13C19 15.7614 16.7614 18 14 18H10C7.23858 18 5 15.7614 5 13V12" 
          stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M12 18V22" stroke="white" strokeWidth="2" strokeLinecap="round"/>
  </svg>
);

// Voice Sample Component for Signup
const VoiceSampleSignup = ({ onComplete, onCancel, email }) => {
  const [challengeString, setChallengeString] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioStreamRef = useRef(null);

  useEffect(() => {
    const randomNumber = Math.floor(100000 + Math.random() * 900000).toString();
    setChallengeString(randomNumber);
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: true
      });
      
      audioStreamRef.current = stream;
      const mediaRecorder = new MediaRecorder(stream);
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
      };
      
      mediaRecorder.start();
      setIsRecording(true);
      
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
      
    } catch (err) {
      setError('Please allow microphone access');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
      }
    }
  };

  const submitRecording = async () => {
    if (!audioBlob) {
      setError('Please record your voice first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64data = reader.result.split(',')[1];
        localStorage.setItem('signup_voice_sample', base64data);
        localStorage.setItem('signup_challenge_string', challengeString);
        
        onComplete({
          success: true,
          message: 'Voice sample recorded successfully',
          challenge_string: challengeString
        });
      };
      reader.readAsDataURL(audioBlob);
      
    } catch (err) {
      setError('Failed to save voice sample');
    } finally {
      setLoading(false);
    }
  };

  const reRecord = () => {
    setAudioBlob(null);
    setRecordingTime(0);
    const randomNumber = Math.floor(100000 + Math.random() * 900000).toString();
    setChallengeString(randomNumber);
  };

  return (
    <div className="container">
      <div className="card">
        <h2 className="title">Record Voice Sample</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        <div className="challenge-display">
          <div className="challenge-number">{challengeString}</div>
          <p className="instruction">Speak this number clearly</p>
        </div>

        <div className="recording-section">
          <div className="record-button-wrapper">
            <button 
              className={`record-button ${isRecording ? 'recording' : ''}`}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={loading}
            >
              <div className="button-content">
                {isRecording ? (
                  <>
                    <div className="recording-dot"></div>
                    <span>Stop</span>
                  </>
                ) : audioBlob ? (
                  <>
                    <div style={{ fontSize: '24px' }}>✓</div>
                    <span>Recorded</span>
                  </>
                ) : (
                  <>
                    <div style={{ fontSize: '24px' }}>🎤</div>
                    <span>Record</span>
                  </>
                )}
              </div>
            </button>
            {isRecording && (
              <div className="recording-indicator">
                <div className="timer">{recordingTime}s</div>
              </div>
            )}
          </div>
          
          <div className="button-group">
            {audioBlob && (
              <button 
                onClick={submitRecording} 
                className="submit-button"
                disabled={loading}
              >
                {loading ? 'Saving...' : 'Save Sample'}
              </button>
            )}
            {audioBlob && (
              <button 
                onClick={reRecord} 
                className="re-record-button"
              >
                Re-record
              </button>
            )}
            <button 
              onClick={onCancel} 
              className="skip-button"
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Voice Enrollment Component
const VoiceEnrollment = ({ onComplete, onCancel, email }) => {
  const [challengeString, setChallengeString] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioStreamRef = useRef(null);

  useEffect(() => {
    const randomNumber = Math.floor(100000 + Math.random() * 900000).toString();
    setChallengeString(randomNumber);
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: true
      });
      
      audioStreamRef.current = stream;
      const mediaRecorder = new MediaRecorder(stream);
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
      };
      
      mediaRecorder.start();
      setIsRecording(true);
      
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
      
    } catch (err) {
      setError('Please allow microphone access');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
      }
    }
  };

  const submitRecording = async () => {
    if (!audioBlob) {
      setError('Please record your voice first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      formData.append('challenge_string', challengeString);

      const response = await axios.post('/voice/enroll/verify', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });

      if (response.data.success || response.data.voice_enabled) {
        onComplete(response.data);
      } else {
        setError('Enrollment failed');
      }
      
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const reRecord = () => {
    setAudioBlob(null);
    setRecordingTime(0);
    const randomNumber = Math.floor(100000 + Math.random() * 900000).toString();
    setChallengeString(randomNumber);
  };

  return (
    <div className="container">
      <div className="card">
        <h2 className="title">Enable Voice Authentication</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        <div className="challenge-display">
          <div className="challenge-number">{challengeString}</div>
          <p className="instruction">Speak this number clearly</p>
        </div>

        <div className="recording-section">
          <div className="record-button-wrapper">
            <button 
              className={`record-button ${isRecording ? 'recording' : ''}`}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={loading}
            >
              <div className="button-content">
                {isRecording ? (
                  <>
                    <div className="recording-dot"></div>
                    <span>Stop</span>
                  </>
                ) : audioBlob ? (
                  <>
                    <div style={{ fontSize: '24px' }}>✓</div>
                    <span>Recorded</span>
                  </>
                ) : (
                  <>
                    <div style={{ fontSize: '24px' }}>🎤</div>
                    <span>Record</span>
                  </>
                )}
              </div>
            </button>
            {isRecording && (
              <div className="recording-indicator">
                <div className="timer">{recordingTime}s</div>
              </div>
            )}
          </div>
          
          <div className="button-group">
            {audioBlob && (
              <button 
                onClick={submitRecording} 
                className="submit-button"
                disabled={loading}
              >
                {loading ? 'Saving...' : 'Submit'}
              </button>
            )}
            {audioBlob && (
              <button 
                onClick={reRecord} 
                className="re-record-button"
              >
                Re-record
              </button>
            )}
            <button 
              onClick={onCancel} 
              className="skip-button"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Voice Login Component
const VoiceLogin = ({ onSuccess, onBack, onEnable, onPasswordLogin }) => {
  const [email, setEmail] = useState(getLastUsedEmail() || '');
  const [challengeString, setChallengeString] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(1);
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioStreamRef = useRef(null);

  useEffect(() => {
    if (email) {
      checkVoiceEnabled();
    }
  }, [email]);

  const checkVoiceEnabled = async () => {
    if (!email) {
      setError('No email found');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post('/voice/login/challenge', {
        email: email.trim()
      });

      if (response.data.challenge_string) {
        setChallengeString(response.data.challenge_string);
        setVoiceEnabled(true);
        setStep(2);
      } else {
        setVoiceEnabled(false);
        setStep(3);
      }
    } catch (err) {
      if (err.response && err.response.status === 400 && 
          err.response.data.detail && 
          err.response.data.detail.includes('Voice authentication not enabled')) {
        setVoiceEnabled(false);
        setStep(3);
      } else {
        setError(extractErrorMessage(err));
      }
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: true
      });
      
      audioStreamRef.current = stream;
      const mediaRecorder = new MediaRecorder(stream);
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
      };
      
      mediaRecorder.start();
      setIsRecording(true);
      
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
      
    } catch (err) {
      setError('Please allow microphone access');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
      }
    }
  };

  const submitLogin = async () => {
    if (!audioBlob) {
      setError('Please record your voice first');
      return;
    }

    if (!challengeString) {
      setError('No challenge received');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      formData.append('email', email);
      formData.append('challenge_string', challengeString);

      const response = await axios.post('/voice/login/verify', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        localStorage.setItem('access_token', response.data.access_token);
        localStorage.setItem('refresh_token', response.data.refresh_token);
        setUserData({
          user_id: response.data.user_id,
          email: response.data.email,
          voice_enabled: true
        });
        
        setLastUsedEmail(response.data.email);
        onSuccess(response.data);
      }
      
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const reRecord = () => {
    setAudioBlob(null);
    setRecordingTime(0);
  };

  const handleEnableVoice = () => {
    onEnable(email);
  };

  const handlePasswordLogin = () => {
    onPasswordLogin(email);
  };

  if (step === 3) {
    return (
      <div className="container">
        <div className="card">
          <h2 className="title">Voice Login Not Enabled</h2>
          
          <div className="user-profile-header" style={{ marginBottom: '30px' }}>
            <div className="profile-display">
              <ProfileAvatar email={email} size={48} />
              <div className="profile-info">
                <div className="profile-email">{email}</div>
                <div className="profile-status">Voice authentication is not enabled for this account</div>
              </div>
            </div>
          </div>
          
          <div className="button-group">
            <button 
              onClick={handleEnableVoice} 
              className="primary-button"
            >
              Enable Voice Authentication
            </button>
            
            <button 
              onClick={handlePasswordLogin} 
              className="secondary-button"
            >
              Login with Password Instead
            </button>
            
            <div className="account-link-section">
              <span className="account-link-text">Want to use a different account? </span>
              <button 
                onClick={onBack}
                className="account-link-button"
              >
                Go Back
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="card">
        <h2 className="title">Voice Login</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        {email && (
          <div className="user-profile-header">
            <div className="profile-display">
              <ProfileAvatar email={email} size={48} />
              <div className="profile-info">
                <div className="profile-email">{email}</div>
                <div className="profile-status">Ready for voice verification</div>
              </div>
            </div>
          </div>
        )}
        
        {loading && !challengeString ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <p>Checking voice authentication status...</p>
          </div>
        ) : challengeString ? (
          <div>
            <div className="challenge-display">
              <div className="challenge-number">{challengeString}</div>
              <p className="instruction">Speak this number clearly</p>
            </div>

            <div className="recording-section">
              <div className="record-button-wrapper">
                <button 
                  className={`record-button ${isRecording ? 'recording' : ''}`}
                  onClick={isRecording ? stopRecording : startRecording}
                  disabled={loading}
                >
                  <div className="button-content">
                    {isRecording ? (
                      <>
                        <div className="recording-dot"></div>
                        <span>Stop</span>
                      </>
                    ) : audioBlob ? (
                      <>
                        <div style={{ fontSize: '24px' }}>✓</div>
                        <span>Recorded</span>
                      </>
                    ) : (
                      <>
                        <div style={{ fontSize: '24px' }}>🎤</div>
                        <span>Record</span>
                      </>
                    )}
                  </div>
                </button>
                {isRecording && (
                  <div className="recording-indicator">
                    <div className="timer">{recordingTime}s</div>
                  </div>
                )}
              </div>
              
              <div className="button-group">
                {audioBlob && (
                  <button 
                    onClick={submitLogin} 
                    className="submit-button"
                    disabled={loading}
                  >
                    {loading ? 'Verifying...' : 'Submit'}
                  </button>
                )}
                {audioBlob && (
                  <button 
                    onClick={reRecord} 
                    className="re-record-button"
                  >
                    Re-record
                  </button>
                )}
                
                <div className="account-link-section">
                  <span className="account-link-text">Not {email}? </span>
                  <button 
                    onClick={onBack}
                    className="account-link-button"
                  >
                    Use different account
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <p>Loading voice authentication...</p>
          </div>
        )}
      </div>
    </div>
  );
};

// Main App Component
const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showSignup, setShowSignup] = useState(false);
  const [showVoiceSample, setShowVoiceSample] = useState(false);
  const [showVoiceEnrollment, setShowVoiceEnrollment] = useState(false);
  const [showVoiceLogin, setShowVoiceLogin] = useState(false);
  
  // Initialize with empty forms, last used email is stored separately
  const [loginData, setLoginData] = useState({ 
    email: '', 
    password: '', 
    rememberMe: true 
  });
  const [signupData, setSignupData] = useState({ 
    email: '', 
    password: '', 
    confirmPassword: '',
    enableVoice: false
  });
  
  const [loginError, setLoginError] = useState('');
  const [signupError, setSignupError] = useState('');
  const [loading, setLoading] = useState(false);
  const [userInfo, setUserInfo] = useState(getUserData());

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const userData = getUserData();
    if (token && userData) {
      setIsLoggedIn(true);
      setUserInfo(userData);
      // Don't auto-fill login form when logged in
    }
  }, []);

  // Clear form data when switching between login/signup
  useEffect(() => {
    if (showSignup) {
      // Only prefill signup email if coming from login with email
      if (loginData.email && loginData.email !== getLastUsedEmail()) {
        setSignupData(prev => ({ ...prev, email: loginData.email }));
      } else {
        setSignupData({ 
          email: '', 
          password: '', 
          confirmPassword: '',
          enableVoice: false
        });
      }
    } else {
      // When switching to login, only prefill with last used email
      const lastEmail = getLastUsedEmail() || '';
      setLoginData(prev => ({ 
        ...prev, 
        email: lastEmail,
        password: '' // Always clear password
      }));
    }
  }, [showSignup, loginData.email]);

  const handleSignup = async (e) => {
    e.preventDefault();
    
    if (!signupData.email.trim()) {
      setSignupError('Email is required');
      return;
    }
    
    if (!signupData.password) {
      setSignupError('Password is required');
      return;
    }
    
    if (signupData.password.length < 6) {
      setSignupError('Password must be at least 6 characters');
      return;
    }
    
    if (signupData.password !== signupData.confirmPassword) {
      setSignupError('Passwords do not match');
      return;
    }

    setLoading(true);
    setSignupError('');

    try {
      await axios.post('/signup', {
        email: signupData.email.trim(),
        password: signupData.password
      });

      // Save the email as last used (for voice login)
      setLastUsedEmail(signupData.email);
      
      // Clear ALL form data after successful signup
      setSignupData({ 
        email: '', 
        password: '', 
        confirmPassword: '',
        enableVoice: false
      });
      
      setLoginData({
        email: signupData.email, // Prefill login email for convenience
        password: '',
        rememberMe: true
      });
      
      // Switch to login page
      setShowSignup(false);
      setSignupError('');
      
    } catch (err) {
      setSignupError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    
    if (!loginData.email.trim()) {
      setLoginError('Email is required');
      return;
    }
    
    if (!loginData.password) {
      setLoginError('Password is required');
      return;
    }
    
    setLoading(true);
    setLoginError('');
    
    try {
      const response = await axios.post('/login', {
        email: loginData.email.trim(),
        password: loginData.password
      });
      
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('refresh_token', response.data.refresh_token);
      setUserData({
        user_id: response.data.user_id,
        email: response.data.email,
        voice_enabled: response.data.voice_enabled
      });
      
      // Save email as last used (for voice login)
      setLastUsedEmail(response.data.email);
      
      setIsLoggedIn(true);
      setUserInfo({
        user_id: response.data.user_id,
        email: response.data.email,
        voice_enabled: response.data.voice_enabled
      });
      
      // Clear login form after successful login
      setLoginData({
        email: '', // Clear form
        password: '',
        rememberMe: true
      });
      
    } catch (err) {
      setLoginError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    clearUserData();
    setIsLoggedIn(false);
    setUserInfo(null);
    setShowVoiceSample(false);
    setShowVoiceEnrollment(false);
    setShowVoiceLogin(false);
    setLoginError('');
    setSignupError('');
    // Don't clear last used email - keep it for voice login convenience
    setLoginData({ email: '', password: '', rememberMe: true });
  };

  const handleVoiceEnrollmentComplete = (data) => {
    setShowVoiceEnrollment(false);
    if (userInfo) {
      setUserInfo({ ...userInfo, voice_enabled: true });
    }
    
    const currentUserData = getUserData();
    if (currentUserData) {
      setUserData({ ...currentUserData, voice_enabled: true });
    }
  };

  const handleVoiceLoginSuccess = (data) => {
    setIsLoggedIn(true);
    setUserInfo({
      user_id: data.user_id,
      email: data.email,
      voice_enabled: true
    });
    setLastUsedEmail(data.email);
    setShowVoiceLogin(false);
  };

  const handleVoiceSampleComplete = (data) => {
    setShowVoiceSample(false);
    setSignupData(prev => ({ ...prev, enableVoice: true }));
  };

  const handleVoiceLoginClick = () => {
    const lastEmail = getLastUsedEmail();
    if (!lastEmail) {
      setLoginError('No account found. Please sign up or login first.');
      return;
    }
    
    setShowVoiceLogin(true);
  };

  const handleVoiceSampleClick = () => {
    setShowVoiceSample(true);
  };

  const handleEnableVoiceForAccount = (email) => {
    // Set login data and redirect to password login
    setLoginData({ 
      email: email, 
      password: '', // Don't prefill password
      rememberMe: true 
    });
    setShowVoiceLogin(false);
    setShowSignup(false);
    setLoginError('Please login with password first to enable voice authentication');
  };

  const handlePasswordLoginForAccount = (email) => {
    setLoginData({ 
      email: email, 
      password: '', // Don't prefill password
      rememberMe: true 
    });
    setShowVoiceLogin(false);
    setShowSignup(false);
  };

  const toggleSignup = () => {
    setShowSignup(!showSignup);
    // Clear errors when switching
    setLoginError('');
    setSignupError('');
    
    if (!showSignup) {
      // When going to signup from login, prefill with login email if available
      if (loginData.email) {
        setSignupData(prev => ({ ...prev, email: loginData.email }));
      }
    } else {
      // When going back to login from signup, prefill with last used email
      const lastEmail = getLastUsedEmail() || '';
      setLoginData(prev => ({ 
        ...prev, 
        email: lastEmail,
        password: '' // Always clear password
      }));
    }
  };

  if (showVoiceSample) {
    return <VoiceSampleSignup 
      onComplete={handleVoiceSampleComplete} 
      onCancel={() => setShowVoiceSample(false)}
    />;
  }

  if (showVoiceEnrollment) {
    return <VoiceEnrollment 
      onComplete={handleVoiceEnrollmentComplete} 
      onCancel={() => setShowVoiceEnrollment(false)}
      email={userInfo?.email || getLastUsedEmail() || ''}
    />;
  }

  if (showVoiceLogin) {
    return <VoiceLogin 
      onSuccess={handleVoiceLoginSuccess} 
      onBack={() => setShowVoiceLogin(false)}
      onEnable={handleEnableVoiceForAccount}
      onPasswordLogin={handlePasswordLoginForAccount}
    />;
  }

  if (isLoggedIn && userInfo) {
    return (
      <div className="container">
        <div className="card">
          <h2 className="title">Welcome!</h2>
          
          <div className="user-info">
            <div className="profile-display" style={{ marginBottom: '15px' }}>
              <ProfileAvatar email={userInfo.email} size={60} />
              <div className="profile-info">
                <div className="profile-email" style={{ fontSize: '18px', fontWeight: '600' }}>
                  {userInfo.email}
                </div>
                <div className="profile-status">
                  <span className={userInfo.voice_enabled ? 'enabled' : 'disabled'}>
                    Voice Auth: {userInfo.voice_enabled ? 'ENABLED' : 'DISABLED'}
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          <div className="button-group">
            {!userInfo.voice_enabled ? (
              <button 
                onClick={() => setShowVoiceEnrollment(true)} 
                className="primary-button"
              >
                Enable Voice Auth
              </button>
            ) : (
              <button 
                onClick={handleVoiceLoginClick} 
                className="secondary-button"
              >
                Test Voice Login
              </button>
            )}
            
            <button onClick={handleLogout} className="logout-button">
              Logout
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Signup Page
  if (showSignup) {
    return (
      <div className="container">
        <div className="card">
          <h2 className="title">Create Account</h2>

          <form onSubmit={handleSignup} className="form">
            <input 
              className="input" 
              type="email" 
              placeholder="Email (e.g., user@example.com)" 
              value={signupData.email} 
              onChange={e => {
                setSignupData({...signupData, email: e.target.value});
                setSignupError('');
              }} 
              required 
              autoComplete="username email"
            />
            <input 
              className="input" 
              placeholder="Password (min 6 characters)" 
              type="password" 
              value={signupData.password} 
              onChange={e => setSignupData({...signupData, password: e.target.value})} 
              minLength="6" 
              required 
              autoComplete="new-password"
            />
            <input 
              className="input" 
              placeholder="Confirm Password" 
              type="password" 
              value={signupData.confirmPassword} 
              onChange={e => setSignupData({...signupData, confirmPassword: e.target.value})} 
              required 
              autoComplete="new-password"
            />
            
            {signupError && <div className="error-message">{signupError}</div>}
            
            <div className="button-group">
              <button type="submit" className="primary-button" disabled={loading}>
                {loading ? 'Creating...' : 'Create Account'}
              </button>
              
              <div className="button-separator"></div>
              
              <div className="voice-login-wrapper">
                <div 
                  className={`voice-login-option ${signupData.enableVoice ? 'selected' : ''}`}
                  onClick={handleVoiceSampleClick}
                >
                  <div className="voice-login-icon">
                    <VoiceIcon />
                  </div>
                  <button type="button" className="voice-login-text">
                    {signupData.enableVoice ? 'Voice sample recorded ✓' : 'Record voice sample'}
                  </button>
                </div>
              </div>
              
              <div className="account-link-section">
                <span className="account-link-text">Already have an account? </span>
                <button 
                  type="button"
                  onClick={toggleSignup}
                  className="account-link-button"
                >
                  Go Back to Login
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // Login Page
  return (
    <div className="container">
      <div className="card">
        <h2 className="title">Login</h2>

        <form onSubmit={handleLogin} className="form">
          <input 
            className="input" 
            type="email" 
            placeholder="Email (e.g., user@example.com)" 
            value={loginData.email} 
            onChange={e => {
              setLoginData({...loginData, email: e.target.value});
              setLoginError('');
              // Don't save as last used while typing
            }} 
            required 
            autoComplete="username email"
          />
          <input 
            className="input" 
            placeholder="Password" 
            type="password" 
            value={loginData.password} 
            onChange={e => setLoginData({...loginData, password: e.target.value})} 
            required 
            autoComplete="current-password"
          />
          
          {loginError && <div className="error-message">{loginError}</div>}
          
          <div className="form-options">
            <label className="checkbox-label">
              <input 
                type="checkbox" 
                className="checkbox"
                checked={loginData.rememberMe} 
                onChange={e => {
                  setLoginData({...loginData, rememberMe: e.target.checked});
                  if (e.target.checked && loginData.email) {
                    setLastUsedEmail(loginData.email);
                  }
                }} 
              />
              <span>Remember Me</span>
            </label>
          </div>
          
          <div className="button-group">
            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? 'Logging in...' : 'Login'}
            </button>
            
            <div className="button-separator"></div>
            
            <div className="voice-login-wrapper">
              <div 
                className="voice-login-option"
                onClick={handleVoiceLoginClick}
              >
                <div className="voice-login-icon">
                  <VoiceIcon />
                </div>
                <button type="button" className="voice-login-text">
                  Login with voice
                </button>
              </div>
            </div>
            
            <div className="account-link-section">
              <span className="account-link-text">Don't have an account? </span>
              <button 
                type="button"
                onClick={toggleSignup}
                className="account-link-button"
              >
                Create!
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default App;