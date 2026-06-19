import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const SESSION_COOKIE = 'agrimatch_session'

async function parseSession(raw: string | undefined): Promise<{ role: string } | null> {
  if (!raw) return null

  const secret = process.env.SESSION_SECRET

  try {
    const dot = raw.lastIndexOf('.')

    if (!secret || dot === -1) {
      // Dev mode or old unsigned cookie — parse without verification
      const payload = dot !== -1 ? raw.slice(0, dot) : raw
      const s = JSON.parse(atob(payload))
      if (!s.role || !s.exp || s.exp < Date.now()) return null
      return s
    }

    // Verify HMAC-SHA256 signature using Web Crypto (Edge-compatible)
    const payload = raw.slice(0, dot)
    const sig     = raw.slice(dot + 1)
    const enc     = new TextEncoder()

    const key = await crypto.subtle.importKey(
      'raw', enc.encode(secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false, ['verify'],
    )

    // Signature is hex — convert to bytes
    const sigBytes = new Uint8Array(
      (sig.match(/.{2}/g) ?? []).map(b => parseInt(b, 16))
    )

    const valid = await crypto.subtle.verify('HMAC', key, sigBytes, enc.encode(payload))
    if (!valid) return null

    const s = JSON.parse(atob(payload))
    if (!s.role || !s.exp || s.exp < Date.now()) return null
    return s
  } catch {
    return null
  }
}

export async function middleware(request: NextRequest) {
  if (!process.env.SESSION_SECRET && process.env.NODE_ENV === 'production') {
    return new NextResponse('Service misconfigured', { status: 503 })
  }

  const { pathname } = request.nextUrl
  const user = await parseSession(request.cookies.get(SESSION_COOKIE)?.value)

  const isAdmin     = pathname.startsWith('/admin')
  const isSeller    = pathname.startsWith('/seller')
  const isCart      = pathname === '/shop/cart'
  const isDashboard = pathname === '/dashboard'
  const isAuth      = pathname === '/login' || pathname === '/signup'

  // Already logged in — bounce away from auth pages
  if (isAuth && user) {
    const dest =
      user.role === 'admin'  ? '/admin' :
      user.role === 'seller' ? '/seller' : '/'
    return NextResponse.redirect(new URL(dest, request.url))
  }

  // Admin routes — require admin role
  if (isAdmin) {
    if (!user) {
      const url = new URL('/login', request.url)
      url.searchParams.set('from', pathname)
      return NextResponse.redirect(url)
    }
    if (user.role !== 'admin') {
      return NextResponse.redirect(new URL('/?error=forbidden', request.url))
    }
  }

  // Seller routes — require seller or admin
  if (isSeller) {
    if (!user) {
      const url = new URL('/login', request.url)
      url.searchParams.set('from', pathname)
      return NextResponse.redirect(url)
    }
    if (user.role !== 'seller' && user.role !== 'admin') {
      return NextResponse.redirect(new URL('/?error=forbidden', request.url))
    }
  }

  // Cart and buyer dashboard — require any logged-in account
  if ((isCart || isDashboard) && !user) {
    const url = new URL('/login', request.url)
    url.searchParams.set('from', pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/admin/:path*', '/seller/:path*', '/shop/cart', '/dashboard', '/login', '/signup'],
}
