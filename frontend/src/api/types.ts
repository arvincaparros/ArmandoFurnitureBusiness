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
  is_active: boolean
  created_at: string
}
