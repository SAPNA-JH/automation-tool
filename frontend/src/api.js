// Backend base URL. Empty (default) = same-origin. In production set VITE_API_URL in Vercel.
export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

const TOKEN_KEY = 'glitch_token'
export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))

const json = async (r) => {
  if (r.status === 401) {
    setToken(null)
    // let the app-level guard redirect to /login
    throw new Error('unauthorized')
  }
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`
    try {
      const body = await r.json()
      if (body && body.detail) detail = body.detail // surface the API's plain-English error
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return r.json()
}

const call = (path, opts = {}) => {
  const headers = { ...(opts.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  return fetch(`${API_BASE}${path}`, { ...opts, headers }).then(json)
}

const jsonBody = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  // auth
  googleLogin: (credential, refCode = '') =>
    call('/api/auth/google', jsonBody('POST', { credential, ref_code: refCode })),
  devLogin: (email, name, refCode = '') =>
    call('/api/auth/dev-login', jsonBody('POST', { email, name, ref_code: refCode })),
  // plan & referrals
  plan: () => call('/api/plan'),
  applyReferral: (code) => call('/api/referral/apply', jsonBody('POST', { code })),
  // automation mode
  automation: () => call('/api/automation'),
  setAutomation: (body) => call('/api/automation', jsonBody('PUT', body)),
  me: () => call('/api/auth/me'),
  // content
  meta: () => call('/api/meta'),
  stats: () => call('/api/stats'),
  posts: (filters = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
    ).toString()
    return call(`/api/posts${qs ? `?${qs}` : ''}`)
  },
  patchPost: (id, body) => call(`/api/posts/${id}`, jsonBody('PATCH', body)),
  deletePost: (id) => call(`/api/posts/${id}`, { method: 'DELETE' }),
  generate: (body) => call('/api/generate', jsonBody('POST', body)),
  regenerate: (id) => call(`/api/posts/${id}/regenerate`, { method: 'POST' }),
  jobs: () => call('/api/jobs'),
  settings: () => call('/api/settings'),
  niches: () => call('/api/niches'),
  applyNiche: (body) => call('/api/niche', jsonBody('POST', body)),
  saveSettings: (body) => call('/api/settings', jsonBody('PUT', body)),
  // instagram
  igStatus: () => call('/api/instagram/status'),
  igProfile: () => call('/api/instagram/profile'),
  igConfig: (body) => call('/api/instagram/config', jsonBody('PUT', body)),
  igAuthUrl: () => call('/api/instagram/auth-url'),
  igVerify: () => call('/api/instagram/verify'),
  igTestPost: () => call('/api/instagram/test-post', { method: 'POST' }),
  igSettings: (body) => call('/api/instagram/settings', jsonBody('POST', body)),
  igPublish: (id) => call(`/api/instagram/publish/${id}`, { method: 'POST' }),
  igDisconnect: () => call('/api/instagram/disconnect', { method: 'DELETE' }),
}

export const imageUrl = (post) => post.media_url || `${API_BASE}/posts/${post.id}/image`
export const previewUrl = (design) => `${API_BASE}/static/previews/${design}.png`
