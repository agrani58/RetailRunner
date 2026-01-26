import React, { useState, useEffect, useRef, useCallback } from 'react';
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

// Response interceptor - FIXED: Don't auto-reload on 401
axios.interceptors.response.use(
  response => response,
  error => {
    // Only handle network errors, not authentication errors
    if (error.message.includes('Network Error')) {
      console.error('Network error:', error);
    }
    // Don't auto-reload on any error
    return Promise.reject(error);
  }
);

const extractErrorMessage = (error) => {
  if (error.response && error.response.data) {
    const data = error.response.data;
    if (typeof data === 'string') return data;
    if (data.detail) return data.detail;
    if (data.message) return data.message;
    if (data.error) return data.error;
    if (data.voice_message) return data.voice_message;
  }
  return error.message || 'An error occurred';
};

const getLastUsedEmail = () => {
  try {
    return localStorage.getItem('last_used_email');
  } catch {
    return null;
  }
};

const setLastUsedEmail = (email) => {
  try {
    localStorage.setItem('last_used_email', email);
  } catch {}
};

const getUserData = () => {
  try {
    const data = localStorage.getItem('user_data');
    return data ? JSON.parse(data) : null;
  } catch {
    return null;
  }
};

const setUserData = (data) => {
  try {
    localStorage.setItem('user_data', JSON.stringify(data));
  } catch {}
};

const setTokens = (accessToken, refreshToken) => {
  try {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
  } catch {}
};

const getTokens = () => {
  try {
    return {
      accessToken: localStorage.getItem('access_token'),
      refreshToken: localStorage.getItem('refresh_token')
    };
  } catch {
    return { accessToken: null, refreshToken: null };
  }
};

const clearUserData = () => {
  try {
    localStorage.removeItem('user_data');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('last_used_email');
  } catch {}
};

const getInitials = (email) => {
  if (!email) return '?';
  const parts = email.split('@')[0];
  const nameParts = parts.split(/[._]/);
  if (nameParts.length >= 2) {
    return (nameParts[0][0] + nameParts[1][0]).toUpperCase();
  }
  return parts[0].toUpperCase();
};

const ProfileAvatar = ({ email, size = 32 }) => {
  const initials = getInitials(email);
  
  return (
    <div 
      className="profile-avatar"
      style={{
        width: size,
        height: size,
        backgroundColor: '#00a651',
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

const VoiceIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
);

// Voice Sample Component for Signup with REAL-TIME validation
const VoiceSampleSignup = ({ onComplete, onCancel, email }) => {
  const [challengeString, setChallengeString] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [spokenText, setSpokenText] = useState('');
  const [validationFailed, setValidationFailed] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioStreamRef = useRef(null);

  const generateNewChallenge = () => {
    const randomNumber = Math.floor(100000 + Math.random() * 900000).toString();
    setChallengeString(randomNumber);
    return randomNumber;
  };

  useEffect(() => {
    generateNewChallenge();
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
      
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        
        // Automatically validate the recording
        await validateRecording(blob);
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

  const validateRecording = async (blob) => {
    setLoading(true);
    setError('');
    setSuccess(false);
    setValidationFailed(false);
    
    try {
      const formData = new FormData();
      formData.append('audio', blob, 'recording.webm');
      formData.append('challenge_text', challengeString);
      
      // Send to real-time validation endpoint
      const response = await axios.post('/voice/verify/challenge-speech', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });
      
      if (response.data.success) {
        setSuccess(true);
        setSpokenText(response.data.spoken_text);
        setError('');
        
        // Convert blob to base64 and pass to parent
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64data = reader.result.split(',')[1];
          
          onComplete({
            success: true,
            challenge_string: challengeString,
            voiceSample: base64data,
            spoken_text: response.data.spoken_text,
            validation_passed: true
          });
        };
        reader.readAsDataURL(blob);
      } else {
        setError('Could not validate. Please try again.');
        setSuccess(false);
        setValidationFailed(true);
      }
      
    } catch (err) {
      // Show specific error message
      const errorMsg = extractErrorMessage(err);
      setError(errorMsg || 'Could not validate. Please try again.');
      setSuccess(false);
      setValidationFailed(true);
    } finally {
      setLoading(false);
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

  const reRecord = () => {
    setAudioBlob(null);
    setSuccess(false);
    setError('');
    setRecordingTime(0);
    setSpokenText('');
    setValidationFailed(false);
    
    // Generate new challenge string immediately
    generateNewChallenge();
  };

  const handleSkip = () => {
    onComplete({
      success: false,
      challenge_string: null,
      voiceSample: null,
      validation_passed: false,
      skipped: true
    });
  };

  return (
    <div className="container">
      <div className="card">
        <h2 className="title">Record Voice Sample</h2>
        
        <div className="challenge-display">
          <div className="challenge-number">{challengeString}</div>
          <p className="instruction">Speak this number clearly</p>
        </div>

        <div className="recording-section">
          <div className="record-button-wrapper">
            <button 
              className={`record-button ${isRecording ? 'recording' : ''} ${success ? 'success' : ''} ${validationFailed ? 'failed' : ''}`}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={loading || success || validationFailed}
            >
              <div className="button-content">
                {loading ? (
                  <>
                    <div className="spinner"></div>
                    <span>Validating...</span>
                  </>
                ) : isRecording ? (
                  <>
                    <div className="recording-dot"></div>
                    <span>Stop</span>
                  </>
                ) : success ? (
                  <>
                    <div style={{ fontSize: '24px' }}>✓</div>
                    <span>Validated</span>
                  </>
                ) : validationFailed ? (
                  <>
                    <div style={{ fontSize: '24px' }}>✗</div>
                    <span>Failed</span>
                  </>
                ) : audioBlob ? (
                  <>
                    <span>Recorded</span>
                  </>
                ) : (
                  <>
                    <div style={{ width: '40px', height: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <div className="voice-login-icon">
                        <VoiceIcon />
                      </div>
                    </div>
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
            {error && (
              <div style={{ 
                color: '#ff3b30',
                fontSize: '14px',
                textAlign: 'center',
                margin: '10px 0'
              }}>
                {error}
              </div>
            )}
            
          
            
            {audioBlob && !success && (
              <button 
                onClick={reRecord} 
                className="re-record-button"
                disabled={loading}
              >
                Re-record
              </button>
            )}
            
            <button 
              onClick={handleSkip} 
              className="skip-button"
              disabled={loading}
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Voice Enrollment Component (Updated)
const VoiceEnrollment = ({ onComplete, onCancel, email, isUpdate = false }) => {
  const [challengeText, setChallengeText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [gettingChallenge, setGettingChallenge] = useState(false);
  const [validationFailed, setValidationFailed] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioStreamRef = useRef(null);

  // Store email on component mount
  useEffect(() => {
    if (email) {
      setLastUsedEmail(email.trim().toLowerCase());
    }
  }, [email]);

  const getNewChallenge = useCallback(async () => {
    setGettingChallenge(true);
    setError('');
    setSuccess(false);
    setAudioBlob(null);
    setChallengeText('');
    setValidationFailed(false);
    
    try {
      const endpoint = isUpdate ? '/voice/profile/update/challenge' : '/voice/enroll/challenge';
      const response = await axios.get(endpoint);
      setChallengeText(response.data.challenge_text);
    } catch (err) {
      setError('Could not get challenge');
    } finally {
      setGettingChallenge(false);
    }
  }, [isUpdate]);

  useEffect(() => {
    getNewChallenge();
  }, [getNewChallenge]);

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
      
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        
        // Automatically submit the recording
        await submitRecording(blob);
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

  const submitRecording = async (blob) => {
    if (!challengeText) {
      setError('No challenge received');
      return;
    }

    setLoading(true);
    setError('');
    setValidationFailed(false);

    try {
      const formData = new FormData();
      formData.append('audio', blob, 'recording.webm');
      formData.append('challenge_text', challengeText);

      const endpoint = isUpdate ? '/voice/profile/update/verify' : '/voice/enroll/verify';
      const response = await axios.post(endpoint, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });

      if (response.data.success) {
        setSuccess(true);
        setTimeout(() => {
          onComplete(response.data);
        }, 1000);
      } else {
        setError('Could not validate');
        setValidationFailed(true);
      }
      
    } catch (err) {
      const errorMsg = extractErrorMessage(err);
      setError(errorMsg || 'Could not validate');
      setValidationFailed(true);
    } finally {
      setLoading(false);
    }
  };

  const reRecord = () => {
    setAudioBlob(null);
    setRecordingTime(0);
    setError('');
    setSuccess(false);
    setValidationFailed(false);
    // Get a new challenge when re-recording
    getNewChallenge();
  };

  return (
    <div className="container">
      <div className="card">
        <h2 className="title">
          {isUpdate ? 'Update Voice Sample' : 'Enable Voice Authentication'}
        </h2>
        
        <div className="challenge-display">
          <div className="challenge-number">
            {challengeText}
          </div>
          <p className="instruction">Speak this number clearly</p>
        </div>

        <div className="recording-section">
          <div className="record-button-wrapper">
            <button 
              className={`record-button ${isRecording ? 'recording' : ''} ${success ? 'success' : ''} ${validationFailed ? 'failed' : ''}`}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={loading || !challengeText || gettingChallenge || success || validationFailed}
            >
              <div className="button-content">
                {loading ? (
                  <>
                    <div className="spinner"></div>
                   
                  </>
                ) : isRecording ? (
                  <>
                    <div className="recording-dot"></div>
                    <span>Stop</span>
                  </>
                ) : success ? (
                  <>
                    <div style={{ fontSize: '24px' }}>✓</div>
                    <span>Complete</span>
                  </>
                ) : validationFailed ? (
                  <>
                    <div style={{ fontSize: '24px' }}>✗</div>
                    <span>Failed</span>
                  </>
                ) : audioBlob ? (
                  <>
                    <span>Recorded</span>
                  </>
                ) : (
                  <>
                    <div style={{ width: '40px', height: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <div className="voice-login-icon">
                        <VoiceIcon />
                      </div>
                    </div>
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
            {error && (
              <div style={{ 
                color: '#ff3b30',
                fontSize: '14px',
                textAlign: 'center',
                margin: '10px 0'
              }}>
                {error}
              </div>
            )}
            
            {success && (
              <div style={{ 
                color: '#00a651',
                fontSize: '14px',
                textAlign: 'center',
                margin: '10px 0'
              }}>
                Voice profile updated successfully!
              </div>
            )}
            
           
            
            {audioBlob && !success && (
              <button 
                onClick={reRecord} 
                className="re-record-button"
                disabled={loading || gettingChallenge}
              >
                Re-record
              </button>
            )}
            
            <button 
              onClick={onCancel} 
              className="skip-button"
              disabled={loading || gettingChallenge}
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
const VoiceLogin = ({ onSuccess, onBack, onEnable, onPasswordLogin, onSignup }) => {
  const [email, setEmail] = useState('');
  const [challengeText, setChallengeText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(1);
  const [gettingChallenge, setGettingChallenge] = useState(false);
  const [success, setSuccess] = useState(false);
  const [validationFailed, setValidationFailed] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioStreamRef = useRef(null);

  // Load last used email on component mount
  useEffect(() => {
    const lastEmail = getLastUsedEmail();
    if (lastEmail) {
      setEmail(lastEmail);
    }
  }, []);

  const checkVoiceEnabled = useCallback(async () => {
    if (!email.trim()) {
      setError('Please enter your email');
      return;
    }

    setGettingChallenge(true);
    setError('');

    try {
      // Store email before making the request
      const normalizedEmail = email.trim().toLowerCase();
      setLastUsedEmail(normalizedEmail);
      
      const response = await axios.get('/voice/login/challenge', {
        params: { email: normalizedEmail }
      });

      if (response.data.challenge_text) {
        setChallengeText(response.data.challenge_text);
        setStep(2);
      }
    } catch (err) {
      const errorMsg = extractErrorMessage(err);
      if (err.response?.status === 404) {
        setError('Account not found. Please sign up first.');
        setStep(3);
      } else if (err.response?.status === 400) {
        if (errorMsg.includes('Voice authentication is not enabled')) {
          setError('Voice authentication is not enabled for this account.');
          setStep(4);
        } else {
          setError(errorMsg || 'Could not get challenge');
        }
      } else if (err.response?.status === 429) {
        setError('Too many attempts. Please try again later.');
      } else {
        setError(errorMsg || 'Could not get challenge');
      }
    } finally {
      setGettingChallenge(false);
    }
  }, [email]);

  const getNewChallenge = useCallback(async () => {
    if (!email.trim()) return;
    
    setGettingChallenge(true);
    setError('');
    setAudioBlob(null);
    setChallengeText('');
    setSuccess(false);
    setValidationFailed(false);
    
    try {
      const normalizedEmail = email.trim().toLowerCase();
      setLastUsedEmail(normalizedEmail);
      
      const response = await axios.get('/voice/login/challenge', {
        params: { email: normalizedEmail }
      });

      if (response.data.challenge_text) {
        setChallengeText(response.data.challenge_text);
      }
    } catch (err) {
      const errorMsg = extractErrorMessage(err);
      setError(errorMsg || 'Could not get challenge');
    } finally {
      setGettingChallenge(false);
    }
  }, [email]);

  useEffect(() => {
    // Only auto-check if we have an email and we're on step 1
    if (email && step === 1) {
      // Don't auto-submit, just wait for user to click continue
    }
  }, [email, step]);

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
      
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        
        // Automatically submit the recording
        await submitLogin(blob);
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

  const submitLogin = async (blob) => {
    if (!challengeText) {
      setError('No challenge received');
      return;
    }

    setLoading(true);
    setError('');
    setValidationFailed(false);

    try {
      const normalizedEmail = email.trim().toLowerCase();
      
      // Convert blob to base64
      const base64Audio = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64data = reader.result.split(',')[1];
          resolve(base64data);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
      
      const requestData = {
        email: normalizedEmail,
        audio_data: base64Audio,
        challenge_text: challengeText
      };

      const response = await axios.post('/voice/login/verify', requestData);

      if (response.data.success) {
        setSuccess(true);
        setTokens(response.data.access_token, response.data.refresh_token);
        
        setUserData({
          id: response.data.user_data.id,
          email: response.data.user_data.email,
          voice_enabled: response.data.user_data.voice_enabled
        });
        
        // Store the email that was used for login
        setLastUsedEmail(response.data.user_data.email);
        
        // Delay success callback for better UX
        setTimeout(() => {
          onSuccess(response.data);
        }, 1000);
      } else {
        setError('Could not validate');
        setValidationFailed(true);
      }
      
    } catch (err) {
      let errorMessage = 'Could not validate';
      
      // Handle specific error cases
      if (err.response?.status === 400) {
        errorMessage = extractErrorMessage(err) || 'Could not validate';
        // Get a new challenge for expired challenges
        if (errorMessage.includes('expired')) {
          setTimeout(() => {
            getNewChallenge();
          }, 500);
        }
      } else if (err.response?.status === 401) {
        errorMessage = extractErrorMessage(err) || 'Could not validate';
      } else if (err.response?.status === 404) {
        errorMessage = 'Account not found';
      } else if (err.response?.status === 429) {
        errorMessage = 'Too many attempts. Please try again later.';
      } else {
        errorMessage = extractErrorMessage(err) || 'Could not validate';
      }
      
      setError(errorMessage);
      setValidationFailed(true);
    } finally {
      setLoading(false);
    }
  };

  const reRecord = () => {
    setAudioBlob(null);
    setRecordingTime(0);
    setError('');
    setSuccess(false);
    setValidationFailed(false);
    // Get a new challenge when re-recording
    getNewChallenge();
  };

  const handleEnableVoice = () => {
    const normalizedEmail = email.trim().toLowerCase();
    setLastUsedEmail(normalizedEmail);
    onEnable(normalizedEmail);
  };

  const handlePasswordLogin = () => {
    const normalizedEmail = email.trim().toLowerCase();
    setLastUsedEmail(normalizedEmail);
    onPasswordLogin(normalizedEmail);
  };

  const handleSignup = () => {
    const normalizedEmail = email.trim().toLowerCase();
    setLastUsedEmail(normalizedEmail);
    onSignup(normalizedEmail);
  };

  if (step === 1) {
    return (
      <div className="container">
        <div className="card">
          <h2 className="title">Voice Login</h2>
          
          <div className="form">
            <input 
              className="input" 
              type="email" 
              placeholder="Enter your email" 
              value={email} 
              onChange={e => {
                setEmail(e.target.value);
                setError('');
              }}
            />
            
            {error && (
              <div style={{ 
                color: '#ff3b30',
                fontSize: '14px',
                textAlign: 'center',
                margin: '10px 0'
              }}>
                {error}
              </div>
            )}
            
            <div className="button-group">
              <button 
                onClick={checkVoiceEnabled} 
                className="primary-button"
                disabled={gettingChallenge || !email.trim()}
              >
                {gettingChallenge ? 'Checking...' : 'Continue'}
              </button>
              
              <button 
                onClick={onBack} 
                className="secondary-button"
                disabled={gettingChallenge}
              >
                Go Back
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (step === 2) {
    return (
      <div className="container">
        <div className="card">
          <h2 className="title">Voice Login</h2>
          
          <div className="user-profile-header">
            <div className="profile-display">
              <ProfileAvatar email={email} size={48} />
              <div className="profile-info">
                <div className="profile-email">{email}</div>
                <div className="profile-status">Ready for voice verification</div>
              </div>
            </div>
          </div>
          
          <div className="challenge-display">
            <div className="challenge-number">
              {challengeText}
            </div>
            <p className="instruction">Speak this number clearly</p>
          </div>

          <div className="recording-section">
            <div className="record-button-wrapper">
              <button 
                className={`record-button ${isRecording ? 'recording' : ''} ${success ? 'success' : ''} ${validationFailed ? 'failed' : ''}`}
                onClick={isRecording ? stopRecording : startRecording}
                disabled={loading || !challengeText || gettingChallenge || success || validationFailed}
              >
                <div className="button-content">
                  {loading ? (
                    <>
                      <div className="spinner"></div>
                      <span>Verifying...</span>
                    </>
                  ) : isRecording ? (
                    <>
                      <div className="recording-dot"></div>
                      <span>Stop</span>
                    </>
                  ) : success ? (
                    <>
                      <div style={{ fontSize: '24px' }}>✓</div>
                      <span>Success</span>
                    </>
                  ) : validationFailed ? (
                    <>
                      <span>Failed</span>
                    </>
                  ) : audioBlob ? (
                    <>
                      <span>Recorded</span>
                    </>
                  ) : (
                    <>
                      <div style={{ width: '40px', height: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <div className="voice-login-icon">
                          <VoiceIcon />
                        </div>
                      </div>
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
              {error && (
                <div style={{ 
                  color: '#ff3b30',
                  fontSize: '14px',
                  textAlign: 'center',
                  margin: '10px 0'
                }}>
                  {error}
                </div>
              )}
              

           
              
              {audioBlob && !success && (
                <button 
                  onClick={reRecord} 
                  className="re-record-button"
                  disabled={loading || gettingChallenge}
                >
                  Re-record
                </button>
              )}
              
              <button 
                onClick={() => {
                  setStep(1);
                  setAudioBlob(null);
                  setError('');
                  setSuccess(false);
                  setValidationFailed(false);
                }} 
                className="secondary-button"
                disabled={loading || gettingChallenge}
              >
                Use different email
              </button>
              
              <button 
                onClick={onBack} 
                className="skip-button"
                disabled={loading || gettingChallenge}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (step === 3) {
    return (
      <div className="container">
        <div className="card">
          <h2 className="title">Account Not Found</h2>
          
          <div className="user-profile-header" style={{ marginBottom: '30px' }}>
            <div className="profile-display">
              <ProfileAvatar email={email} size={48} />
              <div className="profile-info">
                <div className="profile-email">{email}</div>
                <div className="profile-status">This email is not registered</div>
              </div>
            </div>
          </div>
          
          <div className="button-group">
            <button 
              onClick={handleSignup} 
              className="primary-button"
            >
              Sign Up Now
            </button>
            
            <button 
              onClick={() => {
                setStep(1);
                setError('');
              }} 
              className="secondary-button"
            >
              Try Different Email
            </button>
            
            <button 
              onClick={onBack} 
              className="skip-button"
            >
              Go Back to Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (step === 4) {
    return (
      <div className="container">
        <div className="card">
          <h2 className="title">Voice Not Enabled</h2>
          
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
            
            <button 
              onClick={onBack} 
              className="skip-button"
            >
              Go Back to Login
            </button>
          </div>
        </div>
      </div>
    );
  }
};

// Main App Component
const App = () => {
  const [currentView, setCurrentView] = useState('initial');
  const [userInfo, setUserInfo] = useState(null);
  
  const [loginData, setLoginData] = useState({ 
    email: getLastUsedEmail() || '', 
    password: ''
  });
  const [signupData, setSignupData] = useState({ 
    email: '', 
    password: '', 
    confirmPassword: '',
    enableVoice: false,
    voiceSample: null,
    challengeText: null,
    spokenText: '',
    validationPassed: false
  });
  
  const [loginError, setLoginError] = useState('');
  const [signupError, setSignupError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const tokens = getTokens();
    const userData = getUserData();
    
    if (tokens.accessToken && tokens.refreshToken && userData) {
      setUserInfo(userData);
      setCurrentView('dashboard');
      
      axios.get('/auth/me')
        .then(response => {
          setUserInfo(response.data);
          setUserData(response.data);
        })
        .catch(() => {
          clearUserData();
          setUserInfo(null);
          setCurrentView('login');
        });
    } else {
      setUserInfo(null);
      setCurrentView('login');
    }
  }, []);

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
      const requestData = {
        email: signupData.email.trim().toLowerCase(), // Convert to lowercase
        password: signupData.password
      };

      // Only include voice data if validation passed
      if (signupData.enableVoice && signupData.validationPassed) {
        requestData.voice_sample = signupData.voiceSample;
        requestData.challenge_text = signupData.challengeText;
      }

      console.log('Signup request:', { ...requestData, voice_sample: requestData.voice_sample ? 'present' : 'not present' });
      const response = await axios.post('/auth/signup', requestData);
      
      console.log('Signup response:', response.data);
      
      // Clear any existing error
      setSignupError('');

      setLastUsedEmail(signupData.email.trim().toLowerCase());
      
      // Reset form data
      setSignupData({ 
        email: '', // Reset to empty
        password: '', 
        confirmPassword: '',
        enableVoice: false,
        voiceSample: null,
        challengeText: null,
        spokenText: '',
        validationPassed: false
      });
      
      // Go directly to login page after signup
      setTimeout(() => {
        setCurrentView('login');
        setLoginData(prev => ({ 
          ...prev, 
          email: signupData.email.trim().toLowerCase(),
          password: ''
        }));
      }, 500);
      
    } catch (err) {
      console.error('Signup error details:', err.response?.data || err.message);
      
      // Extract specific error message from backend
      let errorMessage = 'Could not create account';
      
      if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.response?.data?.message) {
        errorMessage = err.response.data.message;
      } else if (err.response?.status === 400) {
        errorMessage = extractErrorMessage(err) || 'Invalid request. Please check your input.';
      }
      
      setSignupError(errorMessage);
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
      console.log('Login attempt:', { email: loginData.email.trim() });
      const response = await axios.post('/auth/login', {
        email: loginData.email.trim().toLowerCase(), // Convert to lowercase
        password: loginData.password
      });
      
      console.log('Login successful:', response.data);
      
      setTokens(response.data.access_token, response.data.refresh_token);
      
      setUserData({
        id: response.data.user_data.id,
        email: response.data.user_data.email,
        voice_enabled: response.data.user_data.voice_enabled
      });
      
      setLastUsedEmail(response.data.user_data.email);
      
      setUserInfo({
        id: response.data.user_data.id,
        email: response.data.user_data.email,
        voice_enabled: response.data.user_data.voice_enabled
      });
      
      setLoginData({
        email: response.data.user_data.email,
        password: ''
      });
      
      setCurrentView('dashboard');
      
    } catch (err) {
      console.error('Login error details:', err.response?.data || err.message);
      
      // Don't auto-reload on login failure
      let errorMessage = 'Login failed';
      
      if (err.response?.status === 401) {
        errorMessage = 'Invalid email or password';
      } else if (err.response?.status === 404) {
        errorMessage = 'Account not found';
      } else if (err.response?.status === 500) {
        errorMessage = 'Server error. Please try again.';
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message.includes('Network Error')) {
        errorMessage = 'Cannot connect to server. Please check your connection.';
      }
      
      setLoginError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await axios.post('/auth/logout');
    } catch (err) {
      console.error('Logout error:', err);
    }
    
    clearUserData();
    setUserInfo(null);
    setCurrentView('login');
    setLoginError('');
    setSignupError('');
    setLoginData({ email: getLastUsedEmail() || '', password: '' });
  };

  const handleVoiceEnrollmentComplete = (data) => {
    if (data.access_token && data.refresh_token) {
      setTokens(data.access_token, data.refresh_token);
    }
    
    if (data.user_data) {
      setUserInfo({ ...data.user_data });
      setUserData({ ...data.user_data });
    }
    
    setCurrentView('dashboard');
  };

  const handleVoiceLoginSuccess = (data) => {
    setUserInfo({
      id: data.user_data.id,
      email: data.user_data.email,
      voice_enabled: data.user_data.voice_enabled
    });
    setLastUsedEmail(data.user_data.email);
    setCurrentView('dashboard');
  };

  const handleVoiceSampleComplete = (data) => {
    setSignupData(prev => ({ 
      ...prev, 
      enableVoice: data.success,
      voiceSample: data.voiceSample,
      challengeText: data.challenge_string,
      spokenText: data.spoken_text,
      validationPassed: data.validation_passed
    }));
    setCurrentView('signup');
  };

  const handleEnableVoiceForAccount = (email) => {
    const normalizedEmail = email.trim().toLowerCase();
    setLastUsedEmail(normalizedEmail);
    setLoginData({ 
      email: normalizedEmail, 
      password: ''
    });
    setCurrentView('login');
    setLoginError('Please login with password first to enable voice authentication');
  };

  const handlePasswordLoginForAccount = (email) => {
    const normalizedEmail = email.trim().toLowerCase();
    setLastUsedEmail(normalizedEmail);
    setLoginData({ 
      email: normalizedEmail, 
      password: ''
    });
    setCurrentView('login');
  };

  const handleSignupForAccount = (email) => {
    const normalizedEmail = email.trim().toLowerCase();
    setLastUsedEmail(normalizedEmail);
    setSignupData(prev => ({ ...prev, email: normalizedEmail }));
    setCurrentView('signup');
  };

  const renderView = () => {
    switch (currentView) {
      case 'voiceSample':
        return (
          <VoiceSampleSignup 
            onComplete={handleVoiceSampleComplete} 
            onCancel={() => setCurrentView('signup')}
            email={signupData.email}
          />
        );
      
      case 'voiceEnrollment':
        return (
          <VoiceEnrollment 
            onComplete={handleVoiceEnrollmentComplete} 
            onCancel={() => setCurrentView('dashboard')}
            email={userInfo?.email || getLastUsedEmail() || ''}
          />
        );
      
      case 'voiceUpdate':
        return (
          <VoiceEnrollment 
            onComplete={handleVoiceEnrollmentComplete} 
            onCancel={() => setCurrentView('dashboard')}
            email={userInfo?.email || getLastUsedEmail() || ''}
            isUpdate={true}
          />
        );
      
      case 'voiceLogin':
        return (
          <VoiceLogin 
            onSuccess={handleVoiceLoginSuccess} 
            onBack={() => setCurrentView('login')}
            onEnable={handleEnableVoiceForAccount}
            onPasswordLogin={handlePasswordLoginForAccount}
            onSignup={handleSignupForAccount}
          />
        );
      
      case 'signup':
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
                
                {signupError && (
                  <div style={{ 
                    color: '#ff3b30',
                    fontSize: '14px',
                    textAlign: 'center',
                    margin: '10px 0'
                  }}>
                    {signupError}
                  </div>
                )}
                
                <div className="button-group">
                  <button type="submit" className="primary-button" disabled={loading}>
                    {loading ? 'Creating...' : 'Create Account'}
                  </button>
                  
                  <div className="button-separator">
                    <span>OR</span>
                  </div>
                  
                  <div className="voice-login-wrapper">
                    <div 
                      className={`voice-login-option ${signupData.enableVoice ? 'selected' : ''}`}
                      onClick={() => setCurrentView('voiceSample')}
                    >
                      <div className="voice-login-icon">
                        <VoiceIcon />
                      </div>
                      <button type="button" className="voice-login-text">
                        {signupData.enableVoice ? 'Voice sample validated ✓' : 'Record voice sample'}
                      </button>
                    </div>
                  </div>
                  
                  <div className="account-link-section">
                    <span className="account-link-text">Already have an account? </span>
                    <button 
                      type="button"
                      onClick={() => setCurrentView('login')}
                      className="account-link-button"
                      disabled={loading}
                    >
                      Go Back to Login
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        );
      
      case 'dashboard':
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
                    onClick={() => setCurrentView('voiceEnrollment')} 
                    className="primary-button"
                  >
                    Enable Voice Auth
                  </button>
                ) : (
                  <button 
                    onClick={() => setCurrentView('voiceUpdate')} 
                    className="primary-button"
                  >
                    Update Voice Sample
                  </button>
                )}
                
                <button onClick={handleLogout} className="logout-button">
                  Logout
                </button>
              </div>
            </div>
          </div>
        );
      
      case 'login':
      default:
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
                  }} 
                  required 
                  autoComplete="username email"
                />
                <input 
                  className="input" 
                  placeholder="Password" 
                  type="password" 
                  value={loginData.password} 
                  onChange={e => {
                    setLoginData({...loginData, password: e.target.value});
                    setLoginError('');
                  }} 
                  required 
                  autoComplete="current-password"
                />
                
                {loginError && (
                  <div style={{ 
                    color: '#ff3b30',
                    fontSize: '14px',
                    textAlign: 'center',
                    margin: '10px 0'
                  }}>
                    {loginError}
                  </div>
                )}
                
                <div className="button-group">
                  <button type="submit" className="primary-button" disabled={loading}>
                    {loading ? 'Logging in...' : 'Login'}
                  </button>
                  
                  <div className="button-separator">
                    <span>OR</span>
                  </div>
                  
                  <div className="voice-login-wrapper">
                    <div 
                      className="voice-login-option"
                      onClick={() => setCurrentView('voiceLogin')}
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
                      onClick={() => {
                        // Reset signup data when going to signup from login
                        setSignupData({ 
                          email: '', 
                          password: '', 
                          confirmPassword: '',
                          enableVoice: false,
                          voiceSample: null,
                          challengeText: null,
                          spokenText: '',
                          validationPassed: false
                        });
                        setCurrentView('signup');
                      }}
                      className="account-link-button"
                      disabled={loading}
                    >
                      Create Account
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        );
    }
  };

  return renderView();
};

export default App;