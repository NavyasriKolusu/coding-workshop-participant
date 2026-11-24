const apiBaseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:3001').replace(/\/$/, '')

/**
 * Send a JSON request to one of the Lambda services.
 * @param {string} service - Backend service name.
 * @param {string} path - Optional service-relative path.
 * @param {object} options - Fetch options with an optional JSON body.
 * @returns {Promise<any>} Parsed JSON response.
 */
export async function apiRequest(service, path = '', options = {}) {
  const token = window.localStorage.getItem('acme-token')
  const headers = { ...options.headers }
  const isLocalProxy = new URL(apiBaseUrl).hostname === 'localhost'

  if (options.body !== undefined || (token && isLocalProxy)) {
    // The local proxy forwards Content-Type but drops Authorization.
    headers['Content-Type'] = token && isLocalProxy
      ? `application/json; acme-token=${token}`
      : 'application/json'
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${apiBaseUrl}/api/${service}${path}`, {
    ...options,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  const payload = response.status === 204 ? null : await response.json()
  if (!response.ok) {
    if (response.status === 401 && path !== '/login') {
      window.localStorage.removeItem('acme-token')
      window.localStorage.removeItem('acme-user')
      window.dispatchEvent(new Event('acme:unauthorized'))
    }
    throw new Error(payload?.error || `Request failed (${response.status})`)
  }
  return payload
}

/**
 * Build a URL query string from non-empty filter values.
 * @param {object} filters - Filter key/value pairs.
 * @returns {string} Encoded query string, or an empty string.
 */
export function queryString(filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })
  const query = params.toString()
  return query ? `?${query}` : ''
}
