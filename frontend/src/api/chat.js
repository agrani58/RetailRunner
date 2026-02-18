const API_URL = import.meta.env.VITE_API_URL

if (!API_URL) {
  throw new Error('VITE_API_URL is not defined')
}

export async function sendMessageToAPI(query, token) {
  const headers = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query }),
  })

  if (!res.ok) {
    const error = await res.text()
    throw new Error(error || 'API error')
  }

  return res.json()
}