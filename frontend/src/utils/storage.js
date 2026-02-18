// Token storage
export const setTokens = (accessToken, refreshToken) => {
  localStorage.setItem('access_token', accessToken)
  localStorage.setItem('refresh_token', refreshToken)
}

export const getAccessToken = () => localStorage.getItem('access_token')
export const getRefreshToken = () => localStorage.getItem('refresh_token')
export const clearTokens = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

// User storage
export const setUser = (user) => {
  localStorage.setItem('user', JSON.stringify(user))
}

export const getUser = () => {
  const user = localStorage.getItem('user')
  return user ? JSON.parse(user) : null
}

export const clearUser = () => {
  localStorage.removeItem('user')
}