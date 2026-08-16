// Single place the access token is read from/written to. Nothing
// outside this file should touch localStorage for the token
// directly - matches the existing convention in
// src/theme/ThemeContext.tsx, the only other localStorage usage in
// the app.

const TOKEN_STORAGE_KEY = 'armando_access_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token)
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}

export function hasToken(): boolean {
  return getToken() !== null
}
