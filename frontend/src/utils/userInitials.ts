// Derives display initials from any whitespace-separated display
// name string (e.g. "Arvin Caparros" -> "AC"). The backend's User
// model (backend/app/database/models.py) has no separate first/last
// name fields - only `username` - so callers pass that as
// displayName; a single-word username naturally yields a single
// initial per the rules below, which is the honest behavior for the
// data that actually exists, not a bug.
export function getUserInitials(
  displayName: string | null | undefined,
): string {
  if (!displayName || !displayName.trim()) {
    return 'U'
  }

  const parts = displayName
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (parts.length === 0) {
    return 'U'
  }

  if (parts.length === 1) {
    return parts[0].charAt(0).toUpperCase()
  }

  // First name = first word; last name = everything from the second
  // word onward (so a compound surname like "Dela Cruz" still yields
  // a single initial from its own first word) - "Juan Dela Cruz" ->
  // "JD", not "JC" from the final word "Cruz".
  const first = parts[0].charAt(0)
  const last = parts[1].charAt(0)

  return `${first}${last}`.toUpperCase()
}
