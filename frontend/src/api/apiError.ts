import { AxiosError } from 'axios'

// FastAPI shapes errors as { "detail": ... }, but "detail" itself
// takes two different forms depending on where it came from:
//   - HTTPException(detail="some message")          -> string
//   - Pydantic/FastAPI request validation (422)      -> array of
//     { type, loc, msg, input, ctx } objects, one per invalid field
// Both are handled below. This file is shared, generic infrastructure
// used by every module - it must not contain logic specific to any
// one feature (Resources, Auth, Dashboard, etc.).

interface FastApiValidationErrorItem {
  msg?: unknown
  loc?: unknown
}

function isValidationErrorItem(
  value: unknown,
): value is FastApiValidationErrorItem {
  return typeof value === 'object' && value !== null
}

// FastAPI's 422 shape: detail is an array of per-field error objects.
// Surfaces the first one, prefixed with the field name when available
// (e.g. "name: String should have at least 1 character").
function extractValidationArrayMessage(
  detail: unknown[],
): string | null {
  const first = detail[0]

  if (!isValidationErrorItem(first) || typeof first.msg !== 'string') {
    return null
  }

  const loc = first.loc

  const field =
    Array.isArray(loc) && loc.length > 0
      ? loc[loc.length - 1]
      : undefined

  return typeof field === 'string' || typeof field === 'number'
    ? `${field}: ${first.msg}`
    : first.msg
}

// Rare, but some error shapes nest a single object rather than an
// array (e.g. a hand-built { "detail": { "msg": "..." } }) - handled
// defensively rather than assumed.
function extractValidationObjectMessage(
  detail: Record<string, unknown>,
): string | null {
  return typeof detail.msg === 'string' ? detail.msg : null
}

export function getApiErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof AxiosError)) {
    return fallback
  }

  if (!error.response) {
    return 'Unable to reach the server. Please check your connection and try again.'
  }

  const detail: unknown = error.response.data?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    return extractValidationArrayMessage(detail) ?? fallback
  }

  if (typeof detail === 'object' && detail !== null) {
    return (
      extractValidationObjectMessage(
        detail as Record<string, unknown>,
      ) ?? fallback
    )
  }

  return fallback
}
