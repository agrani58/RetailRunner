import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL

if (!API_URL) {
  throw new Error('VITE_API_URL is not defined')
}

const client = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' }
})

export async function signup(email, password) {
  const response = await client.post('/signup', { email, password })
  return response.data
}

export async function login(email, password) {
  const response = await client.post('/login', { email, password })
  return response.data
}

export async function logout(refreshToken, accessToken) {
  await client.post('/logout', { refresh_token: refreshToken }, {
    headers: { Authorization: `Bearer ${accessToken}` }
  })
}

export async function refreshAccessToken(refreshToken) {
  const response = await client.post('/refresh', { refresh_token: refreshToken })
  return response.data
}

export async function getCurrentUser(accessToken) {
  const response = await client.get('/me', {
    headers: { Authorization: `Bearer ${accessToken}` }
  })
  return response.data
}