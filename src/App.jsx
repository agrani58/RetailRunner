import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Configure axios with better error handling
axios.defaults.baseURL = API_BASE_URL;
axios.defaults.headers.common['Content-Type'] = 'application/json';

// Request interceptor for auth tokens
axios.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for better error handling
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      // Server responded with error
      return Promise.reject(error);
    } else if (error.request) {
      // Request made but no response
      console.error('Network error:', error.request);
      return Promise.reject(new Error('Network error. Please check your connection.'));
    } else {
      // Something else happened
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
      if (typeof data.detail === 'object') return JSON.stringify(data.detail);
    }
    if (data.message) {
      if (typeof data.message === 'string') return data.message;
    }
    if (data.error) {
      if (typeof data.error === 'string') return data.error;
    }
  }
  return error.message || 'An error occurred';
};

// Secure storage management
const getUserEmail = () => {
  try {
    return localStorage.getItem('user_email');
  } catch (e) {
    console.error('Error getting user email:', e);
    return null;
  }
};

const setUserEmail = (email) => {
  try {
    localStorage.setItem('user_email', email);
  } catch (e) {
    console.error('Error saving user email:', e);
  }
};

const clearUserEmail = () => {
  try {
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_data');
  } catch (e) {
    console.error('Error clearing user data:', e);
  }
};

// Get initials for profile picture (simplified)
const getInitials = (email) => {
  if (!email) return 'U';
  const username = email.split('@')[0];
  return username.charAt(0).toUpperCase();
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

// Mic Icon SVG Component for Recording
const MicIcon = ({ size = 36, color = "white" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 15C13.6569 15 15 13.6569 15 12V6C15 4.34315 13.6569 3 12 3C10.3431 3 9 4.34315 9 6V12C9 13.6569 10.3431 15 12 15Z" 
          stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M19 12V13C19 15.7614 16.7614 18 14 18H10C7.23858 18 5 15.7614 5 13V12" 
          stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M12 18V22" stroke={color} strokeWidth="2" strokeLinecap="round"/>
  </svg>
);

// Check Icon SVG Component
const CheckIcon = ({ size = 36, color = "white" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M20 6L9 17L4 12" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

// Generate random 6-digit number
const generateRandomNumber = () => {
  return Math.floor(100000 + Math.random() * 900000).toString();
};

// Voice Sample Component for Signup
const VoiceSampleSignup = ({ onComplete, onCancel }) => {
  const [challengeText, setChallengeText] = useState('');
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
    // Generate random 6-digit number on component mount
    setChallengeText(generateRandomNumber());
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
      // Store voice sample locally during signup
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64data = reader.result.split(',')[1];
        localStorage.setItem('signup_voice_sample', base64data);
        localStorage.setItem('signup_challenge_text', challengeText);
        localStorage.setItem('signup_voice_recorded', 'true');
        
        onComplete({
          success: true,
          message: 'Voice sample recorded successfully',
          challenge_text: challengeText
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
    // Generate new random number for re-recording
    setChallengeText(generateRandomNumber());
  };

  return (
    <div className="container">
      <div className="card">
        <h2 className="title">Record Voice Sample</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        {/* Random Number Challenge Display */}
        <div className="challenge-display">
          <div className="challenge-number">{challengeText}</div>
          <p className="instruction">Speak this number clearly</p>
          <p className="instruction" style={{ fontSize: '12px', color: '#666' }}>
            This will be used for voice authentication
          </p>
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
                    <CheckIcon size={36} color="white" />
                    <span>Recorded</span>
                  </>
                ) : (
                  <>
                    <MicIcon size={36} color="white" />
                    <span>Record</span>
                  </>
                )}
              </div>
            </button>
            {isRecording && (
              <div className="recording-indicator">
                <div className="pulse-ring"></div>
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

// Voice Enrollment Component (after account creation)
const VoiceEnrollment = ({ onComplete, onCancel, email }) => {
  const [challengeText, setChallengeText] = useState('');
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
    // Generate random 6-digit number
    setChallengeText(generateRandomNumber());
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
      formData.append('challenge_text', challengeText);

      const response = await axios.post('/voice/enroll/verify', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });

      if (response.data.success || response.data.voice_enabled) {
        onComplete(response.data);
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
    // Generate new random number
    setChallengeText(generateRandomNumber());
  };

  return (
    <div className="container">
      <div className="card">
        <h2 className="title">Enable Voice Authentication</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        {/* Random Number Challenge Display */}
        <div className="challenge-display">
          <div className="challenge-number">{challengeText}</div>
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
                    <CheckIcon size={36} color="white" />
                    <span>Recorded</span>
                  </>
                ) : (
                  <>
                    <MicIcon size={36} color="white" />
                    <span>Record</span>
                  </>
                )}
              </div>
            </button>
            {isRecording && (
              <div className="recording-indicator">
                <div className="pulse-ring"></div>
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
              Skip for now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Voice Login Component - Updated with random number challenge
const VoiceLogin = ({ onSuccess, onCancel, userEmail }) => {
  const [email, setEmail] = useState(userEmail || '');
  const [challengeText, setChallengeText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(userEmail ? 2 : 1);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioStreamRef = useRef(null);

  // Auto-request challenge if email is available
  useEffect(() => {
    if (userEmail && step === 2) {
      requestChallenge();
    }
  }, [userEmail, step]);

  const requestChallenge = async () => {
    if (!email) {
      setError('Email is required');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post('/voice/login/challenge', {
        email: email.trim()
      });

      setChallengeText(response.data.challenge_text);
      setStep(2);
    } catch (err) {
      setError(extractErrorMessage(err));
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

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      formData.append('email', email);
      formData.append('challenge_text', challengeText);

      const response = await axios.post('/voice/login/verify', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        localStorage.setItem('access_token', response.data.access_token);
        localStorage.setItem('refresh_token', response.data.refresh_token);
        localStorage.setItem('user_data', JSON.stringify({
          user_id: response.data.user_id,
          email: response.data.email,
          voice_enabled: true
        }));
        
        setUserEmail(response.data.email);
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

  return (
    <div className="container">
      <div className="card">
        <h2 className="title">Voice Login</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        {step === 1 ? (
          <div>
            <div className="form">
              <input
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                disabled={loading}
                autoComplete="username email"
              />
            </div>
            <div className="button-group">
              <button 
                onClick={requestChallenge} 
                className="primary-button"
                disabled={loading || !email}
              >
                {loading ? 'Loading...' : 'Continue'}
              </button>
              <button onClick={onCancel} className="skip-button">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div>
            {/* Random Number Challenge Display for Login */}
            <div className="challenge-display">
              <div className="challenge-number">{challengeText}</div>
              <p className="instruction">Speak this number clearly</p>
              <p className="instruction" style={{ fontSize: '12px', color: '#666' }}>
                Logging in as: {email}
              </p>
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
                        <CheckIcon size={36} color="white" />
                        <span>Recorded</span>
                      </>
                    ) : (
                      <>
                        <MicIcon size={36} color="white" />
                        <span>Record</span>
                      </>
                    )}
                  </div>
                </button>
                {isRecording && (
                  <div className="recording-indicator">
                    <div className="pulse-ring"></div>
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
                <button onClick={() => setStep(1)} className="skip-button">
                  Use Different Email
                </button>
              </div>
            </div>
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
  
  const [loginData, setLoginData] = useState({ 
    email: getUserEmail() || '', 
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
  const [userInfo, setUserInfo] = useState(null);
  const [storedEmail, setStoredEmail] = useState(getUserEmail());

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const userData = localStorage.getItem('user_data');
    if (token && userData) {
      try {
        const user = JSON.parse(userData);
        setIsLoggedIn(true);
        setUserInfo(user);
        setStoredEmail(user.email);
        setUserEmail(user.email);
      } catch {
        localStorage.clear();
        clearUserEmail();
      }
    }
    
    // Check for stored email on load
    const email = getUserEmail();
    if (email) {
      setStoredEmail(email);
    }
  }, []);

  const handleSignup = async (e) => {
    e.preventDefault();
    
    if (signupData.password !== signupData.confirmPassword) {
      setSignupError('Passwords do not match');
      return;
    }

    setLoading(true);
    setSignupError('');

    try {
      // Create account with better error handling
      const signupResponse = await axios.post('/signup', {
        email: signupData.email.trim(),
        password: signupData.password
      });

      // Login to get token
      const loginResponse = await axios.post('/login', {
        email: signupData.email.trim(),
        password: signupData.password
      });

      // Store tokens
      localStorage.setItem('access_token', loginResponse.data.access_token);
      localStorage.setItem('refresh_token', loginResponse.data.refresh_token);
      localStorage.setItem('user_data', JSON.stringify({
        user_id: loginResponse.data.user_id,
        email: signupData.email,
        voice_enabled: false
      }));

      setUserEmail(signupData.email);
      
      // Set user info
      const newUserInfo = {
        user_id: loginResponse.data.user_id,
        email: signupData.email,
        voice_enabled: false
      };
      
      setUserInfo(newUserInfo);
      setIsLoggedIn(true);
      setStoredEmail(signupData.email);
      
      // Check if voice sample was recorded during signup
      const voiceSample = localStorage.getItem('signup_voice_sample');
      const challengeText = localStorage.getItem('signup_challenge_text');
      
      if (voiceSample && challengeText) {
        // Enroll the recorded voice sample
        try {
          const formData = new FormData();
          
          // Convert base64 to blob
          const byteCharacters = atob(voiceSample);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          const audioBlob = new Blob([byteArray], { type: 'audio/webm' });
          
          formData.append('audio', audioBlob, 'recording.webm');
          formData.append('challenge_text', challengeText);

          const enrollResponse = await axios.post('/voice/enroll/verify', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            }
          });

          if (enrollResponse.data.success) {
            setUserInfo(prev => ({ ...prev, voice_enabled: true }));
            // Clear temporary voice data
            localStorage.removeItem('signup_voice_sample');
            localStorage.removeItem('signup_challenge_text');
            localStorage.removeItem('signup_voice_recorded');
          }
        } catch (enrollErr) {
          console.error('Voice enrollment failed:', enrollErr);
          // Continue without voice enrollment
        }
      }
      
      setShowSignup(false);
      
    } catch (err) {
      const errorMsg = extractErrorMessage(err);
      setSignupError(errorMsg || 'Failed to create account. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setLoginError('');
    
    try {
      const response = await axios.post('/login', {
        email: loginData.email.trim(),
        password: loginData.password
      });
      
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('refresh_token', response.data.refresh_token);
      localStorage.setItem('user_data', JSON.stringify({
        user_id: response.data.user_id,
        email: response.data.email,
        voice_enabled: response.data.voice_enabled
      }));
      
      setUserEmail(response.data.email);
      setStoredEmail(response.data.email);
      
      setIsLoggedIn(true);
      setUserInfo({
        user_id: response.data.user_id,
        email: response.data.email,
        voice_enabled: response.data.voice_enabled
      });
      
    } catch (err) {
      setLoginError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    clearUserEmail();
    setIsLoggedIn(false);
    setUserInfo(null);
    setShowVoiceSample(false);
    setShowVoiceEnrollment(false);
    setShowVoiceLogin(false);
    setLoginError('');
    setSignupError('');
    setStoredEmail('');
    setLoginData({ email: '', password: '', rememberMe: true });
  };

  const handleVoiceEnrollmentComplete = (data) => {
    setShowVoiceEnrollment(false);
    setUserInfo(prev => ({ ...prev, voice_enabled: true }));
  };

  const handleVoiceLoginSuccess = (data) => {
    setIsLoggedIn(true);
    setUserInfo({
      user_id: data.user_id,
      email: data.email,
      voice_enabled: true
    });
    setStoredEmail(data.email);
    setUserEmail(data.email);
    setShowVoiceLogin(false);
  };

  const handleVoiceSampleComplete = (data) => {
    setShowVoiceSample(false);
    setSignupData(prev => ({ ...prev, enableVoice: true }));
  };

  const handleVoiceLoginClick = () => {
    // Use stored email if available, otherwise use login form email
    const emailToUse = storedEmail || loginData.email;
    
    if (!emailToUse) {
      setLoginError('Please enter your email first');
      return;
    }
    
    setUserEmail(emailToUse);
    setStoredEmail(emailToUse);
    setShowVoiceLogin(true);
  };

  const handleVoiceSampleClick = () => {
    setShowVoiceSample(true);
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
      email={userInfo?.email}
    />;
  }

  if (showVoiceLogin) {
    return <VoiceLogin 
      onSuccess={handleVoiceLoginSuccess} 
      onCancel={() => setShowVoiceLogin(false)}
      userEmail={storedEmail}
    />;
  }

  if (isLoggedIn && userInfo) {
    return (
      <div className="container">
        <div className="card">
          <h2 className="title">Welcome!</h2>
          
          <div className="user-info">
            <p><strong>Email:</strong> {userInfo.email}</p>
            <p>
              <strong>Voice Auth:</strong> 
              <span className={userInfo.voice_enabled ? 'enabled' : 'disabled'}>
                {userInfo.voice_enabled ? 'ENABLED' : 'DISABLED'}
              </span>
            </p>
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
                onClick={() => {
                  setStoredEmail(userInfo.email);
                  setShowVoiceLogin(true);
                }} 
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
              placeholder="Email" 
              value={signupData.email} 
              onChange={e => setSignupData({...signupData, email: e.target.value})} 
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
              
              {/* Separator Line */}
              <div className="button-separator">
               
              </div>
              
              {/* Centered Voice Enable Option */}
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
              
              {/* Account Link */}
              <div className="account-link-section">
                <span className="account-link-text">Have an account? </span>
                <button 
                  type="button"
                  onClick={() => {
                    setShowSignup(false);
                    setSignupError('');
                  }}
                  className="account-link-button"
                >
                  Login
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
            placeholder="Email" 
            value={loginData.email} 
            onChange={e => {
              setLoginData({...loginData, email: e.target.value});
              setUserEmail(e.target.value);
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
                    setUserEmail(loginData.email);
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
            
            {/* Separator Line */}
            <div className="button-separator">
              
            </div>
            
            {/* Centered Voice Login Option */}
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
            
            {/* Account Link */}
            <div className="account-link-section">
              <span className="account-link-text">Don't have an account? </span>
              <button 
                type="button"
                onClick={() => {
                  setShowSignup(true);
                  setLoginError('');
                }}
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