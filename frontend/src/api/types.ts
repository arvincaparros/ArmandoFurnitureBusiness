// Mirrors backend/app/schemas/auth.py exactly - field names are the
// wire contract, not UI naming. If the UI ever wants different
// names, add an adapter layer rather than renaming these.

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface UserResponse {
  id: number
  username: string
  email: string
  is_active: boolean
  created_at: string
}

// Shared success-message shape used by register/change-password/
// forgot-password/reset-password - matches backend's MessageResponse.
export interface MessageResponse {
  detail: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  confirm_password: string
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
  confirm_password: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  token: string
  new_password: string
  confirm_password: string
}
