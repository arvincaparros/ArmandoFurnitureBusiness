import {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react'

import {
  fetchCurrentUser,
  loginRequest,
  logoutRequest,
} from '../api/authApi'

import { setUnauthorizedHandler } from '../api/client'

import {
  getToken,
  hasToken,
  removeToken,
  setToken,
} from '../api/tokenStorage'

import type { UserResponse } from '../api/types'

type AuthStatus =
  | 'initializing'
  | 'authenticated'
  | 'unauthenticated'

interface AuthContextValue {
  status: AuthStatus
  user: UserResponse | null
  login: (
    username: string,
    password: string,
  ) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext =
  createContext<AuthContextValue | null>(null)

export function AuthProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [status, setStatus] =
    useState<AuthStatus>('initializing')

  const [user, setUser] =
    useState<UserResponse | null>(null)

  useEffect(() => {
    const clearAuth = () => {
      removeToken()
      setUser(null)
      setStatus('unauthenticated')
    }

    // Any future authenticated request anywhere in the app (not
    // just /me) that comes back 401 flows through this same path,
    // so a session that expires mid-use ends up in exactly the
    // same state as one that was never valid on load.
    setUnauthorizedHandler(clearAuth)

    const initialize = async () => {
      if (!hasToken()) {
        setStatus('unauthenticated')
        return
      }

      try {
        const currentUser = await fetchCurrentUser()

        setUser(currentUser)
        setStatus('authenticated')
      } catch {
        clearAuth()
      }
    }

    initialize()
  }, [])

  const login = async (
    username: string,
    password: string,
  ) => {
    const { access_token } = await loginRequest({
      username,
      password,
    })

    setToken(access_token)

    const currentUser = await fetchCurrentUser()

    setUser(currentUser)
    setStatus('authenticated')
  }

  const logout = async () => {
    try {
      if (getToken()) {
        await logoutRequest()
      }
    } catch {
      // Stateless JWT: the backend cannot revoke an already-issued
      // token (see backend/app/routers/auth.py). This call is
      // best-effort only - clearing the local token below is what
      // actually ends the session, regardless of whether this
      // request succeeded.
    } finally {
      removeToken()
      setUser(null)
      setStatus('unauthenticated')
    }
  }

  return (
    <AuthContext.Provider
      value={{ status, user, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error(
      'useAuth must be used inside AuthProvider',
    )
  }

  return context
}
