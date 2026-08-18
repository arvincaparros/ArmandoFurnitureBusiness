import axios from 'axios'

import { getToken } from './tokenStorage'

// VITE_API_URL is a Vite BUILD-TIME substitution - it gets baked into
// the JS bundle when `vite build` runs, not read at runtime in the
// browser. Locally it comes from .env.development
// (VITE_API_URL=http://localhost:8000); in production (Vercel) it
// must be set as a Production environment variable so it's present
// during that build.
//
// If it's ever missing, axios silently falls back to a relative
// baseURL, which resolves every request against the CURRENT PAGE
// ORIGIN instead of the API - e.g. a Vercel-hosted frontend would
// send "POST /api/auth/register" to the Vercel domain itself rather
// than the Render backend. vercel.json's SPA catch-all rewrite then
// serves index.html for that path, and Vercel returns 405 Method Not
// Allowed for the POST - a confusing failure with no indication that
// the real problem is a missing build-time env var. Failing fast here
// instead turns that into an immediate, actionable error.
if (import.meta.env.PROD && !import.meta.env.VITE_API_URL) {
  throw new Error(
    'VITE_API_URL is not set for this production build. ' +
      'Set it as a Production environment variable in Vercel (e.g. ' +
      'https://your-api.onrender.com) and redeploy - otherwise API ' +
      'requests silently target this site\'s own origin instead of ' +
      'the backend.',
  )
}

// One shared instance for every backend call. Module-level (not a
// hook) so it can be imported from anywhere - React components and
// future non-React service files alike - without creating a second
// Axios instance per module.
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = getToken()

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

type UnauthorizedHandler = () => void

let unauthorizedHandler: UnauthorizedHandler | null = null

// AuthContext registers itself here on mount. Kept decoupled this
// way (rather than importing AuthContext directly) because this
// module sits below React in the dependency graph and must not
// import from it - AuthContext imports this file, not the other
// way around.
export function setUnauthorizedHandler(
  handler: UnauthorizedHandler,
): void {
  unauthorizedHandler = handler
}

// Endpoints where a 401 means "the credentials you supplied in this
// request are wrong" rather than "your session/token is invalid" -
// login's 401 is a wrong username/password; change-password's 401 is
// a wrong current_password on an otherwise-valid, still-authenticated
// session. Neither should trigger the same auto-logout path as a
// real session expiry, or the caller's own inline error handling
// would never be reached before getting redirected to /login.
const CREDENTIAL_CHECK_ENDPOINTS = [
  '/api/auth/login',
  '/api/auth/change-password',
]

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const requestUrl: string = error.config?.url ?? ''

    const isCredentialCheck = CREDENTIAL_CHECK_ENDPOINTS.some(
      (endpoint) => requestUrl.includes(endpoint),
    )

    if (status === 401 && !isCredentialCheck) {
      unauthorizedHandler?.()
    }

    return Promise.reject(error)
  },
)

export default apiClient
