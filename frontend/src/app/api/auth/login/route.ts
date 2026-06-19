import { NextRequest, NextResponse } from 'next/server'
import { createHmac, timingSafeEqual } from 'crypto'

function safeEqual(a: string, b: string): boolean {
  const bufA = Buffer.from(a, 'utf8')
  const bufB = Buffer.from(b, 'utf8')
  const len  = Math.max(bufA.length, bufB.length)
  const padA = Buffer.alloc(len)
  const padB = Buffer.alloc(len)
  bufA.copy(padA)
  bufB.copy(padB)
  return timingSafeEqual(padA, padB)
}

const COOKIE   = 'agrimatch_session'
const MAX_AGE  = 7 * 24 * 60 * 60          // 7 days in seconds
const SECRET   = process.env.SESSION_SECRET ?? ''

// ── Account definitions ───────────────────────────────────────────────────────
// Override any array by setting the corresponding JSON env var in Vercel.
// DEMO_BUYERS_JSON / DEMO_SELLERS_JSON / DEMO_ADMINS_JSON must be valid JSON arrays.

type BuyerAccount  = { id: string; name: string; email: string; password: string; role: string }
type SellerAccount = { id: string; dbId: number; districtId: number; name: string; farmerId: string; phone: string; password: string; role: string }
type AdminAccount  = { id: string; name: string; email: string; password: string; role: string }

function parseEnvAccounts<T>(envVar: string, fallback: T[]): T[] {
  const raw = process.env[envVar]
  if (!raw) return fallback
  try { return JSON.parse(raw) as T[] } catch { return fallback }
}

const DEFAULT_BUYERS: BuyerAccount[] = [
  { id: 'B001', name: 'Akua Asante',  email: 'akua.asante@gmail.com',   password: 'buyer2024', role: 'buyer' },
  { id: 'B002', name: 'Demo Buyer',   email: 'demo.buyer@agrimatch.gh', password: 'demo1234',  role: 'buyer' },
]

const DEFAULT_SELLERS: SellerAccount[] = [
  { id: 'FM-0023', dbId: 11, districtId: 153, name: 'Kofi Mensah', farmerId: 'FM-0023', phone: '0244123456', password: 'farm2024',  role: 'seller' },
  { id: 'FM-0041', dbId: 12, districtId: 200, name: 'Abena Owusu', farmerId: 'FM-0041', phone: '0554987654', password: 'farmer123', role: 'seller' },
]

const DEFAULT_ADMINS: AdminAccount[] = [
  { id: 'ADM001', name: 'Admin', email: 'admin@agrimatch.gh', password: 'admin2024', role: 'admin' },
]

const BUYERS  = parseEnvAccounts<BuyerAccount>('DEMO_BUYERS_JSON',  DEFAULT_BUYERS)
const SELLERS = parseEnvAccounts<SellerAccount>('DEMO_SELLERS_JSON', DEFAULT_SELLERS)
const ADMINS  = parseEnvAccounts<AdminAccount>('DEMO_ADMINS_JSON',  DEFAULT_ADMINS)

// ─────────────────────────────────────────────────────────────────────────────

function signSession(payload: object): string {
  const encoded = Buffer.from(JSON.stringify(payload)).toString('base64')
  if (!SECRET) return encoded                                      // dev: unsigned
  const sig = createHmac('sha256', SECRET).update(encoded).digest('hex')
  return `${encoded}.${sig}`
}

function validateCredentials(
  mode: 'buyer' | 'seller',
  creds: { email?: string; farmerId?: string; phone?: string; password: string },
): object | null {
  const { email = '', farmerId = '', phone = '', password } = creds

  if (mode === 'buyer') {
    const normalEmail = email.toLowerCase().trim()
    const hit =
      BUYERS.find(u => u.email === normalEmail && safeEqual(u.password, password)) ??
      ADMINS.find(u => u.email === normalEmail && safeEqual(u.password, password))
    if (hit) return { id: hit.id, name: hit.name, email: hit.email, role: hit.role }
  }

  if (mode === 'seller') {
    const normalPhone = phone.replace(/[\s\-()]/g, '').replace(/^\+233/, '0')
    const normalId    = farmerId.trim().toUpperCase()
    const hit = SELLERS.find(
      u => (normalId && u.farmerId === normalId) ||
           (normalPhone && u.phone === normalPhone)
    )
    if (hit && safeEqual(hit.password, password))
      return { id: hit.id, dbId: hit.dbId, districtId: hit.districtId, name: hit.name, farmerId: hit.farmerId, phone: hit.phone, role: hit.role }
  }

  return null
}

export async function POST(req: NextRequest) {
  const { mode, email, farmerId, phone, password } = await req.json()

  const user = validateCredentials(mode, { email, farmerId, phone, password })
  if (!user) {
    return NextResponse.json(
      { message: 'Incorrect email, Farmer ID or password.' },
      { status: 401 },
    )
  }

  const session = { ...(user as object), exp: Date.now() + MAX_AGE * 1000 }
  const token   = signSession(session)

  const res = NextResponse.json({ ok: true, role: (user as { role: string }).role })
  res.cookies.set(COOKIE, token, {
    httpOnly: false,          // client JS reads this for the auth context
    secure:   process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    maxAge:   MAX_AGE,
    path:     '/',
  })
  return res
}
