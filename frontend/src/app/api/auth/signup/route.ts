import { NextRequest, NextResponse } from 'next/server'
import { createHmac } from 'crypto'

const COOKIE  = 'agrimatch_session'
const MAX_AGE = 7 * 24 * 60 * 60
const SECRET  = process.env.SESSION_SECRET ?? ''

function signSession(payload: object): string {
  const encoded = Buffer.from(JSON.stringify(payload)).toString('base64')
  if (!SECRET) return encoded
  const sig = createHmac('sha256', SECRET).update(encoded).digest('hex')
  return `${encoded}.${sig}`
}

export async function POST(req: NextRequest) {
  const { id, name, email, phone, farmerId, role } = await req.json()

  if (!name?.trim() || !role) {
    return NextResponse.json({ message: 'Name and role are required.' }, { status: 400 })
  }

  const session = {
    id, name: name.trim(), email: email || undefined,
    phone: phone || undefined, farmerId: farmerId || undefined, role,
    exp: Date.now() + MAX_AGE * 1000,
  }

  const res = NextResponse.json({ ok: true, role })
  res.cookies.set(COOKIE, signSession(session), {
    httpOnly: false,
    secure:   process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    maxAge:   MAX_AGE,
    path:     '/',
  })
  return res
}
