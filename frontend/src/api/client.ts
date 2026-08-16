import axios from 'axios'

import { getToken } from './tokenStorage'

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
