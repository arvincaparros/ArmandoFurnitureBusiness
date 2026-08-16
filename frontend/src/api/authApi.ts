import apiClient from './client'

import type {
  LoginRequest,
  LoginResponse,
  UserResponse,
} from './types'

export async function loginRequest(
  credentials: LoginRequest,
): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>(
    '/api/auth/login',
    credentials,
  )

  return response.data
}

export async function fetchCurrentUser(): Promise<UserResponse> {
  const response = await apiClient.get<UserResponse>(
    '/api/auth/me',
  )

  return response.data
}

export async function logoutRequest(): Promise<void> {
  await apiClient.post('/api/auth/logout')
}
