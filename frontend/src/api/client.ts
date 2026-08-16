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

const LOGIN_ENDPOINT = '/api/auth/login'

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const requestUrl: string = error.config?.url ?? ''

    // A 401 from the login endpoint itself just means "wrong
    // credentials" - the caller is already on the login page and
    // handles that inline. It is not a "your session expired"
    // event and must not trigger the same auto-logout path, or a
    // failed login attempt would look identical to a session
    // timeout and risk a redirect loop back to the page it's
    // already on.
    if (status === 401 && !requestUrl.includes(LOGIN_ENDPOINT)) {
      unauthorizedHandler?.()
    }

    return Promise.reject(error)
  },
)

export default apiClient
