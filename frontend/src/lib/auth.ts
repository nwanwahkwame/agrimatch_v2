export const SESSION_COOKIE  = 'agrimatch_session'
export const SESSION_MAX_AGE = 7 * 24 * 60 * 60   // 7 days (seconds)

export type UserRole = 'buyer' | 'seller' | 'admin'

export interface Session {
  id:          string
  dbId?:       number
  name:        string
  email?:      string
  phone?:      string
  farmerId?:   string
  districtId?: number
  role:        UserRole
  exp:         number    // Unix ms
}

/** Extract numeric farmer ID from session. */
export function farmerDbId(s: Session | null): number {
  if (!s) return 1
  if (s.dbId) return s.dbId
  const n = parseInt((s.farmerId ?? '').replace(/\D/g, ''))
  return isNaN(n) || n === 0 ? 1 : n
}

// ── Client-side session helpers ───────────────────────────────────────────────

/** Read the current session from the cookie (client-side).
 *  Strips the HMAC signature before parsing — verification happens in middleware.
 */
export function getSession(): Session | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${SESSION_COOKIE}=([^;]+)`)
  )
  if (!match) return null
  try {
    // document.cookie returns the raw Set-Cookie value which Next.js may have
    // URL-encoded (e.g. base64 padding '=' becomes '%3D'). Decode before parsing.
    const raw     = decodeURIComponent(match[1])
    // Signed cookies are base64payload.hexsig — strip signature for client read
    const payload = raw.includes('.') ? raw.slice(0, raw.lastIndexOf('.')) : raw
    const s       = JSON.parse(atob(payload)) as Session
    if (!s.role || !s.exp || s.exp < Date.now()) { clearSession(); return null }
    return s
  } catch {
    return null
  }
}

export function clearSession(): void {
  document.cookie = `${SESSION_COOKIE}=; path=/; max-age=0; SameSite=Strict`
}
