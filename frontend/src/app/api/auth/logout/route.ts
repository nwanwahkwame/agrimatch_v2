import { NextRequest, NextResponse } from 'next/server'

const CLEAR = { maxAge: 0, path: '/' }

export async function POST() {
  const res = NextResponse.json({ ok: true })
  res.cookies.set('agrimatch_session', '', CLEAR)
  return res
}

// GET /api/auth/logout — clear cookie and redirect to home
// Used by plain <a href="/api/auth/logout"> links so no JS is needed
export async function GET(req: NextRequest) {
  const home = new URL('/', req.url)
  const res  = NextResponse.redirect(home)
  res.cookies.set('agrimatch_session', '', CLEAR)
  return res
}
