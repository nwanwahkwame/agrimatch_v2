'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Leaf, Eye, EyeOff, ArrowLeft, AlertCircle } from 'lucide-react'

type Mode = 'buyer' | 'seller'
type Step = 'credentials' | 'password'

export default function LoginPage() {
  const [fromPath, setFromPath] = useState('/')
  const [mode, setMode]         = useState<Mode>('buyer')
  const [step, setStep]         = useState<Step>('credentials')
  const [email, setEmail]       = useState('')
  const [farmerId, setFarmerId] = useState('')
  const [phone, setPhone]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [keepIn, setKeepIn]     = useState(true)
  const [error, setError]       = useState('')
  const [showDemo, setShowDemo] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const from   = params.get('from')
    if (from) setFromPath(from)
  }, [])

  function switchMode(m: Mode) {
    setMode(m); setStep('credentials'); setError('')
    setEmail(''); setFarmerId(''); setPhone(''); setPassword('')
  }

  async function handleContinue(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (step === 'credentials') {
      // Basic presence check before moving to password
      if (mode === 'buyer' && !email.trim()) { setError('Enter your email address.'); return }
      if (mode === 'seller' && !farmerId.trim() && !phone.trim()) {
        setError('Enter your Farmer ID or phone number.'); return
      }
      setStep('password')
      return
    }

    // Password step — validate server-side (credentials never leave the server)
    try {
      const res  = await fetch('/api/auth/login', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ mode, email, farmerId, phone, password }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.message ?? 'Login failed.'); return }

      const role = data.role as string
      const dest =
        role === 'admin'  ? '/admin' :
        role === 'seller' ? '/seller' :
        fromPath !== '/login' && fromPath !== '/signup' ? fromPath : '/'
      // Hard redirect: forces full page reload so AuthContext reads the cookie fresh
      window.location.href = dest
    } catch {
      setError('Network error. Please try again.')
    }
  }

  return (
    <div className="min-h-[calc(100vh-100px)] flex flex-col items-center pt-6 pb-10 bg-white">

      {/* Logo */}
      <Link href="/" className="flex items-center gap-1.5 mb-5">
        <Leaf className="h-7 w-7 text-[#22C55E]" strokeWidth={2.5} />
        <span className="font-bold text-2xl text-[#0F1111]">
          agri<span className="text-[#22C55E]">match</span>
        </span>
      </Link>

      {/* Mode tabs */}
      <div className="w-full max-w-sm flex rounded-lg overflow-hidden border border-[#DDDDDD] mb-4 text-sm font-semibold">
        {(['buyer', 'seller'] as Mode[]).map(m => (
          <button
            key={m}
            onClick={() => switchMode(m)}
            className={`flex-1 py-2.5 transition-colors capitalize ${
              mode === m ? 'bg-[#22C55E] text-white' : 'bg-white text-[#565959] hover:bg-[#F0FDF4]'
            }`}
          >
            {m === 'buyer' ? 'Buyer' : 'Farmer / Seller'}
          </button>
        ))}
      </div>

      {/* Card */}
      <div className="w-full max-w-sm border border-[#DDDDDD] rounded-lg px-7 py-6">

        {step === 'password' && (
          <button
            onClick={() => { setStep('credentials'); setError('') }}
            className="flex items-center gap-1 text-xs text-[#007185] hover:underline mb-3"
          >
            <ArrowLeft className="h-3 w-3" />
            Change {mode === 'buyer' ? 'email' : 'ID / phone'}
          </button>
        )}

        <h1 className="text-2xl font-medium text-[#0F1111] mb-1">
          {step === 'credentials'
            ? mode === 'buyer' ? 'Sign in' : 'Farmer sign in'
            : 'Enter your password'}
        </h1>
        {step === 'credentials' && (
          <p className="text-xs text-[#565959] mb-5">
            {mode === 'buyer' ? 'Access your buyer account' : 'Sign in with your Farmer ID or phone number'}
          </p>
        )}

        {/* Error banner */}
        {error && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded px-3 py-2.5 mb-4 text-xs text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        <form onSubmit={handleContinue} className="flex flex-col gap-4">

          {/* ── Buyer: email ── */}
          {mode === 'buyer' && step === 'credentials' && (
            <div className="flex flex-col gap-1">
              <label className="text-sm font-bold text-[#0F1111]">Email address</label>
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="e.g. akua.asante@gmail.com"
                className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] focus:ring-2 focus:ring-[#22C55E]/20"
                autoFocus required
              />
            </div>
          )}

          {/* ── Seller: Farmer ID + phone ── */}
          {mode === 'seller' && step === 'credentials' && (
            <>
              <div className="flex flex-col gap-1">
                <label className="text-sm font-bold text-[#0F1111]">Farmer ID</label>
                <input
                  type="text" value={farmerId} onChange={e => setFarmerId(e.target.value)}
                  placeholder="e.g. FM-0023"
                  className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] focus:ring-2 focus:ring-[#22C55E]/20 uppercase"
                  autoFocus
                />
              </div>
              <div className="relative flex items-center gap-2">
                <div className="flex-1 h-px bg-[#DDDDDD]" />
                <span className="text-xs text-[#767676]">or</span>
                <div className="flex-1 h-px bg-[#DDDDDD]" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm font-bold text-[#0F1111]">Registered phone number</label>
                <div className="flex gap-2">
                  <span className="flex items-center border border-[#888] rounded px-2 text-sm text-[#565959] bg-[#F3F3F3] shrink-0">
                    +233
                  </span>
                  <input
                    type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                    placeholder="0244 123 456"
                    className="flex-1 border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] focus:ring-2 focus:ring-[#22C55E]/20"
                  />
                </div>
              </div>
            </>
          )}

          {/* ── Password step ── */}
          {step === 'password' && (
            <div className="flex flex-col gap-1">
              <div className="bg-[#F7FAF7] border border-[#DDDDDD] rounded px-3 py-2 text-sm text-[#565959] mb-1 font-mono">
                {mode === 'buyer' ? email : (farmerId || `+233 ${phone}`)}
              </div>
              <div className="flex justify-between items-center">
                <label className="text-sm font-bold text-[#0F1111]">Password</label>
                <button type="button" onClick={() => setShowPw(v => !v)}
                  className="text-xs text-[#007185] hover:text-[#15803D] flex items-center gap-0.5">
                  {showPw ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                  {showPw ? 'Hide' : 'Show'}
                </button>
              </div>
              <input
                type={showPw ? 'text' : 'password'} value={password}
                onChange={e => setPassword(e.target.value)}
                className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] focus:ring-2 focus:ring-[#22C55E]/20"
                autoFocus required
              />
            </div>
          )}

          <button type="submit"
            className="w-full bg-[#22C55E] hover:bg-[#16A34A] text-white font-semibold py-2.5 rounded text-sm transition-colors shadow-sm">
            {step === 'credentials' ? 'Continue' : 'Sign in'}
          </button>

          {step === 'password' && (
            <label className="flex items-start gap-2 cursor-pointer">
              <input type="checkbox" checked={keepIn} onChange={e => setKeepIn(e.target.checked)}
                className="mt-0.5 accent-[#22C55E]" />
              <span className="text-xs text-[#0F1111]">Keep me signed in</span>
            </label>
          )}
        </form>

        {step === 'credentials' && (
          <p className="text-xs text-[#565959] mt-4 leading-relaxed">
            By continuing you agree to AgriMatch&apos;s{' '}
            <a href="#" className="text-[#007185] hover:underline">Conditions of Use</a> and{' '}
            <a href="#" className="text-[#007185] hover:underline">Privacy Notice</a>.
          </p>
        )}

        {step === 'password' && (
          <a href="#" className="block text-xs text-[#007185] hover:underline mt-3">
            Forgot your password?
          </a>
        )}

        {step === 'credentials' && (
          <p className="text-xs text-center text-[#565959] mt-4">
            Admin?{' '}
            <span className="text-[#007185]">
              Switch to Buyer tab and use admin@agrimatch.gh
            </span>
          </p>
        )}
      </div>

      {/* Demo credentials */}
      <div className="w-full max-w-sm mt-5">
        <button onClick={() => setShowDemo(v => !v)}
          className="w-full text-xs text-[#007185] hover:underline py-1">
          {showDemo ? 'Hide' : 'Show'} demo credentials
        </button>

        {showDemo && (
          <div className="mt-3 border border-[#DDDDDD] rounded-lg overflow-hidden text-xs">
            <Section title="Buyer accounts">
              <Row label="Akua Asante">
                <p>Email: <Mono>akua.asante@gmail.com</Mono></p>
                <p>Password: <Mono>buyer2024</Mono></p>
              </Row>
              <Row label="Demo Buyer">
                <p>Email: <Mono>demo.buyer@agrimatch.gh</Mono></p>
                <p>Password: <Mono>demo1234</Mono></p>
              </Row>
            </Section>
            <Section title="Farmer / Seller accounts">
              <Row label="Kofi Mensah">
                <p>Farmer ID: <Mono>FM-0023</Mono></p>
                <p>Phone: <Mono>+233 244 123 456</Mono></p>
                <p>Password: <Mono>farm2024</Mono></p>
              </Row>
              <Row label="Abena Owusu">
                <p>Farmer ID: <Mono>FM-0041</Mono></p>
                <p>Phone: <Mono>+233 554 987 654</Mono></p>
                <p>Password: <Mono>farmer123</Mono></p>
              </Row>
            </Section>
            <Section title="Admin account">
              <Row label="Admin">
                <p>Email: <Mono>admin@agrimatch.gh</Mono></p>
                <p>Password: <Mono>admin2024</Mono></p>
              </Row>
            </Section>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="relative w-full max-w-sm my-5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-[#DDDDDD]" />
        </div>
        <div className="relative flex justify-center">
          <span className="px-3 bg-white text-xs text-[#767676]">New to AgriMatch?</span>
        </div>
      </div>

      <Link href="/signup"
        className="w-full max-w-sm border border-[#D5D9D9] bg-[#F0F2F2] hover:bg-[#E7EAEA] rounded px-4 py-2.5 text-sm font-semibold text-[#0F1111] text-center transition-colors shadow-sm">
        Create your AgriMatch account
      </Link>
    </div>
  )
}

// ── Small helpers ────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <>
      <div className="bg-[#F0FDF4] px-4 py-2 font-bold text-[#15803D] border-y border-[#DDDDDD]">
        {title}
      </div>
      {children}
    </>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-2.5 border-b border-[#EEEEEE] last:border-0">
      <p className="font-semibold text-[#0F1111] mb-0.5">{label}</p>
      <div className="flex flex-col gap-0.5 text-[#565959]">{children}</div>
    </div>
  )
}

function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-[#0F1111]">{children}</span>
}
