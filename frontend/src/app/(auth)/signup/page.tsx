'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Leaf, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

type Role = 'buyer' | 'seller'

export default function SignupPage() {
  const { refresh }             = useAuth()
  const router                  = useRouter()
  const [role, setRole]         = useState<Role>('buyer')
  const [name, setName]         = useState('')
  const [email, setEmail]       = useState('')
  const [phone, setPhone]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [error, setError]       = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (!name.trim())        { setError('Enter your full name.'); return }

    const id = role === 'seller'
      ? `FM-${Math.floor(1000 + Math.random() * 8999)}`
      : `B-${Date.now().toString(36).toUpperCase()}`

    try {
      const res = await fetch('/api/auth/signup', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          id,
          name:     name.trim(),
          email:    email.toLowerCase().trim() || undefined,
          phone:    phone ? phone.replace(/[\s-]/g, '') : undefined,
          farmerId: role === 'seller' ? id : undefined,
          role,
        }),
      })
      if (!res.ok) { setError('Account creation failed. Please try again.'); return }
      refresh()
      router.push(role === 'seller' ? '/seller' : '/')
    } catch {
      setError('Network error. Please try again.')
    }
  }

  return (
    <div className="min-h-[calc(100vh-100px)] flex flex-col items-center pt-6 pb-10 bg-white">

      <Link href="/" className="flex items-center gap-1.5 mb-5">
        <Leaf className="h-7 w-7 text-[#22C55E]" strokeWidth={2.5} />
        <span className="font-bold text-2xl text-[#0F1111]">
          agri<span className="text-[#22C55E]">match</span>
        </span>
      </Link>

      <div className="w-full max-w-sm border border-[#DDDDDD] rounded-lg px-7 py-6">
        <h1 className="text-2xl font-medium text-[#0F1111] mb-1">Create account</h1>
        <p className="text-sm text-[#565959] mb-5">Buy or sell fresh produce across Ghana</p>

        {error && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded px-3 py-2.5 mb-4 text-xs text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">

          {/* Role toggle */}
          <div className="flex rounded overflow-hidden border border-[#DDDDDD] text-sm font-semibold">
            {(['buyer', 'seller'] as Role[]).map(r => (
              <button key={r} type="button" onClick={() => setRole(r)}
                className={`flex-1 py-2 transition-colors ${
                  role === r ? 'bg-[#22C55E] text-white' : 'bg-white text-[#565959] hover:bg-[#F0FDF4]'
                }`}>
                {r === 'buyer' ? "I'm a Buyer" : "I'm a Farmer"}
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-sm font-bold text-[#0F1111]">Full name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)}
              placeholder="First and last name"
              className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] focus:ring-2 focus:ring-[#22C55E]/20"
              autoFocus required />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-sm font-bold text-[#0F1111]">
              Mobile number
              {role === 'seller' && <span className="ml-1 text-[#565959] font-normal text-xs">(for USSD access)</span>}
            </label>
            <div className="flex gap-2">
              <span className="flex items-center border border-[#888] rounded px-2 text-sm text-[#565959] bg-[#F3F3F3] shrink-0">
                +233
              </span>
              <input type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                placeholder="20 000 0000"
                className="flex-1 border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] focus:ring-2 focus:ring-[#22C55E]/20"
                required />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-sm font-bold text-[#0F1111]">Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] focus:ring-2 focus:ring-[#22C55E]/20"
              required />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between items-center">
              <label className="text-sm font-bold text-[#0F1111]">Password</label>
              <button type="button" onClick={() => setShowPw(v => !v)}
                className="text-xs text-[#007185] hover:text-[#15803D] flex items-center gap-0.5">
                {showPw ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                {showPw ? 'Hide' : 'Show'}
              </button>
            </div>
            <input type={showPw ? 'text' : 'password'} value={password}
              onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters"
              minLength={8}
              className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] focus:ring-2 focus:ring-[#22C55E]/20"
              required />
            <p className="text-xs text-[#565959]">Minimum 8 characters.</p>
          </div>

          <button type="submit"
            className="w-full bg-[#22C55E] hover:bg-[#16A34A] text-white font-semibold py-2.5 rounded text-sm transition-colors shadow-sm mt-1">
            Create your account
          </button>

          <p className="text-xs text-[#565959] leading-relaxed">
            By creating an account you agree to AgriMatch&apos;s{' '}
            <a href="#" className="text-[#007185] hover:underline">Conditions of Use</a> and{' '}
            <a href="#" className="text-[#007185] hover:underline">Privacy Notice</a>.
          </p>
        </form>
      </div>

      <p className="mt-5 text-sm text-[#565959]">
        Already have an account?{' '}
        <Link href="/login" className="text-[#007185] hover:underline font-semibold">Sign in</Link>
      </p>
    </div>
  )
}
