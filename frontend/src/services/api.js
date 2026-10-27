const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')

async function request(path, options = {}) {
  const headers = new Headers(options.headers)

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers })
  } catch {
    throw new Error('Não foi possível conectar ao StudyBuddy.')
  }

  if (!response.ok) {
    let message = ''
    try {
      const body = await response.json()
      if (Array.isArray(body.errors) && body.errors.length > 0) {
        message = body.errors.map((e) => (e.field ? `${e.field}: ${e.message}` : e.message)).join(' | ')
      } else {
        message = body.detail || body.message || ''
      }
    } catch {
      message = ''
    }
    throw new Error(message || 'Não foi possível concluir a operação.')
  }

  return response.status === 204 ? null : response.json()
}

function authorized(token, options = {}) {
  return request(options.path, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  })
}

export function login(credentials) {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
}

export function register(user) {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(user),
  })
}

export function getCurrentUser(token) {
  return authorized(token, { path: '/api/auth/me' })
}

export function logout(token) {
  return authorized(token, { path: '/api/auth/logout', method: 'POST' })
}

export function listDocuments(token) {
  return authorized(token, { path: '/api/documents' })
}

export function uploadDocument(token, file) {
  const body = new FormData()
  body.append('file', file)
  return authorized(token, { path: '/api/documents', method: 'POST', body })
}

export function deleteDocument(token, documentId) {
  return authorized(token, {
    path: `/api/documents/${documentId}`,
    method: 'DELETE',
  })
}

export function listConversations(token) {
  return authorized(token, { path: '/api/conversations' })
}

export function getConversation(token, conversationId) {
  return authorized(token, { path: `/api/conversations/${conversationId}` })
}

export function askQuestion(token, payload) {
  return authorized(token, {
    path: '/api/chat',
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function unloadModel(token) {
  return authorized(token, {
    path: '/api/ai/unload',
    method: 'POST',
  })
}
