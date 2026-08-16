import apiClient from './client'

import type {
  ChangePasswordRequest,
  ForgotPasswordRequest,
  LoginRequest,
  LoginResponse,
  MessageResponse,
  RegisterRequest,
  ResetPasswordRequest,
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

export async function registerRequest(
  data: RegisterRequest,
): Promise<MessageResponse> {
  const response = await apiClient.post<MessageResponse>(
    '/api/auth/register',
    data,
  )

  return response.data
}

// Uses the shared, already-authenticated apiClient (Authorization
// header attached automatically) - this must be called while logged
// in, unlike register/forgot-password/reset-password below.
export async function changePasswordRequest(
  data: ChangePasswordRequest,
): Promise<MessageResponse> {
  const response = await apiClient.post<MessageResponse>(
    '/api/auth/change-password',
    data,
  )

  return response.data
}

export async function forgotPasswordRequest(
  data: ForgotPasswordRequest,
): Promise<MessageResponse> {
  const response = await apiClient.post<MessageResponse>(
    '/api/auth/forgot-password',
    data,
  )

  return response.data
}

export async function resetPasswordRequest(
  data: ResetPasswordRequest,
): Promise<MessageResponse> {
  const response = await apiClient.post<MessageResponse>(
    '/api/auth/reset-password',
    data,
  )

  return response.data
}
