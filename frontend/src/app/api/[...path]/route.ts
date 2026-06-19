import { NextRequest, NextResponse } from 'next/server'

// Backend URL is server-side only — never exposed to the browser
const BACKEND = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function proxy(req: NextRequest, pathSegments: string[]) {
  const search  = req.nextUrl.search
  const target  = `${BACKEND}/api/${pathSegments.join('/')}${search}`

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const internalSecret = process.env.INTERNAL_API_SECRET
  if (!internalSecret && process.env.NODE_ENV === 'production') {
    return new NextResponse(
      JSON.stringify({ error: 'Service misconfigured' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } },
    )
  }
  if (internalSecret) headers['X-Api-Secret'] = internalSecret

  const init: RequestInit = { method: req.method, headers }

  if (req.method !== 'GET' && req.method !== 'HEAD') {
    const text = await req.text()
    if (text) init.body = text
  }

  const upstream = await fetch(target, { ...init, signal: AbortSignal.timeout(30_000) })
  const body     = await upstream.text()

  return new NextResponse(body, {
    status:  upstream.status,
    headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
  })
}

type Ctx = { params: Promise<{ path: string[] }> }

export async function GET(req: NextRequest, ctx: Ctx) {
  try { return await proxy(req, (await ctx.params).path) }
  catch { return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 }) }
}

export async function POST(req: NextRequest, ctx: Ctx) {
  try { return await proxy(req, (await ctx.params).path) }
  catch { return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 }) }
}

export async function PUT(req: NextRequest, ctx: Ctx) {
  try { return await proxy(req, (await ctx.params).path) }
  catch { return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 }) }
}

export async function PATCH(req: NextRequest, ctx: Ctx) {
  try { return await proxy(req, (await ctx.params).path) }
  catch { return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 }) }
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  try { return await proxy(req, (await ctx.params).path) }
  catch { return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 }) }
}
