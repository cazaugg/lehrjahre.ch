let csrfToken = ''

export function setCsrfToken(token) {
  csrfToken = token || ''
}

export async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) }

  if (csrfToken && options.method && !['GET', 'HEAD'].includes(options.method.toUpperCase())) {
    headers['X-CSRF-Token'] = csrfToken
  }

  let body = options.body
  if (body && !(body instanceof FormData) && typeof body === 'object') {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(body)
  }

  const response = await fetch(path, {
    ...options,
    headers,
    body,
    credentials: 'same-origin'
  })

  const isJson = (response.headers.get('content-type') || '').includes('application/json')
  const payload = isJson ? await response.json() : null

  if (!response.ok) {
    const message = (payload && payload.error) || `Fehler (${response.status})`
    throw new Error(message)
  }

  return payload ? payload.data : null
}
