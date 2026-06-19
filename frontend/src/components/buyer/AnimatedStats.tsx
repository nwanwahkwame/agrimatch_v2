'use client'

import { useEffect, useRef, useState } from 'react'
import { TrendingUp, ShieldCheck, Users, MapPin, Zap, Gift } from 'lucide-react'
import { getAdminStats, getModelAccuracy } from '@/lib/api'

function useCountUp(end: number, duration: number, active: boolean) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!active || end === 0) return
    let t0: number | null = null
    const run = (t: number) => {
      if (!t0) t0 = t
      const p = Math.min((t - t0) / duration, 1)
      setN(Math.round((1 - (1 - p) ** 3) * end))
      if (p < 1) requestAnimationFrame(run)
    }
    requestAnimationFrame(run)
  }, [active, end, duration])
  return n
}

interface Stats {
  active_farmers:  number
  total_markets:   number
  total_value_ghs: number
}

export default function AnimatedStats() {
  const ref  = useRef<HTMLDivElement>(null)
  const [seen, setSeen]   = useState(false)
  const [stats, setStats] = useState<Stats | null>(null)
  const [accuracy, setAccuracy] = useState<number | null>(null)

  // Fetch live stats from DB
  useEffect(() => {
    getAdminStats()
      .then(r => setStats(r.data as Stats))
      .catch(() => {})
    getModelAccuracy()
      .then(r => {
        const rows = r.data as { xgb?: number }[]
        if (rows.length) {
          const avg = rows.reduce((s, x) => s + (x.xgb ?? 0), 0) / rows.length
          setAccuracy(parseFloat(avg.toFixed(1)))
        }
      })
      .catch(() => {})
  }, [])

  // IntersectionObserver — trigger animations when visible
  useEffect(() => {
    const el = ref.current; if (!el) return
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setSeen(true); obs.disconnect() } },
      { threshold: 0.1 }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const valueM   = stats ? Math.max(1, Math.round(stats.total_value_ghs / 1_000_000)) : 0
  const farmersN = stats?.active_farmers ?? 0
  const markets  = stats?.total_markets  ?? 0
  const acc      = accuracy ?? 0

  const ghsVal    = useCountUp(valueM,   2500, seen && !!stats)
  const farmersC  = useCountUp(farmersN, 2000, seen && !!stats)
  const marketsC  = useCountUp(markets,  1800, seen && !!stats)

  // SVG arc for accuracy
  const R = 28, circ = 2 * Math.PI * R
  const [arcOffset, setArcOffset] = useState(circ)
  useEffect(() => {
    if (!seen || acc === 0) return
    const id = setTimeout(() => setArcOffset(circ * (1 - acc / 100)), 200)
    return () => clearTimeout(id)
  }, [seen, acc, circ])

  // Typewriter for speed
  const TW = '< 2 min'
  const [tw, setTw]         = useState('')
  const [twDone, setTwDone] = useState(false)
  useEffect(() => {
    if (!seen) return
    let i = 0
    const id = setInterval(() => {
      setTw(TW.slice(0, ++i))
      if (i >= TW.length) { clearInterval(id); setTwDone(true) }
    }, 110)
    return () => clearInterval(id)
  }, [seen])

  const stagger = (i: number): React.CSSProperties => ({
    opacity:    seen ? 1 : 0,
    transform:  seen ? 'translateY(0)' : 'translateY(24px)',
    transition: `opacity 0.55s ease ${i * 0.1}s, transform 0.55s ease ${i * 0.1}s`,
  })

  return (
    <section ref={ref} className="bg-[#FAFAFA] border-y border-[#E5E5E5] px-4 py-10">
      <style>{`
        @keyframes agri-ripple {
          0%   { transform: scale(0.5); opacity: 0.8 }
          100% { transform: scale(2.4); opacity: 0   }
        }
        @keyframes agri-shimmer {
          0%   { left: -80% }
          100% { left: 140% }
        }
      `}</style>

      <div className="mx-auto max-w-screen-xl">
        <p className="text-center text-[11px] font-bold uppercase tracking-widest text-[#AAAAAA] mb-8">
          Why smart buyers choose AgriMatch
        </p>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">

          {/* 1 — Count-up: produce value (live from declarations) */}
          <div style={stagger(0)} className="flex flex-col items-center gap-3 rounded-2xl bg-gradient-to-br from-[#F0FDF4] to-[#DCFCE7] border border-[#22C55E]/30 p-5 text-center">
            <div className="w-11 h-11 rounded-full bg-[#22C55E]/20 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-[#22C55E] animate-pulse" />
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-[#8B5000] tabular-nums leading-none">
              GHS {ghsVal}M+
            </p>
            <p className="text-xs sm:text-sm text-[#565959] leading-snug">Produce listed this season</p>
          </div>

          {/* 2 — SVG arc: AI accuracy (live from model_baselines) */}
          <div style={stagger(1)} className="flex flex-col items-center gap-3 rounded-2xl bg-gradient-to-br from-[#F4FAF6] to-[#E8F5EE] border border-[#4DB876]/30 p-5 text-center">
            <div className="relative w-12 h-12">
              <svg width="48" height="48" className="absolute inset-0 -rotate-90">
                <circle cx="24" cy="24" r={R} fill="none" stroke="#C8E6D0" strokeWidth="5" />
                <circle
                  cx="24" cy="24" r={R}
                  fill="none" stroke="#1D6B3A" strokeWidth="5"
                  strokeLinecap="round"
                  strokeDasharray={circ}
                  strokeDashoffset={arcOffset}
                  style={{ transition: 'stroke-dashoffset 2.2s cubic-bezier(.4,0,.2,1)' }}
                />
              </svg>
              <ShieldCheck className="absolute inset-0 m-auto h-5 w-5 text-[#1D6B3A]" />
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-[#1D6B3A] leading-none">
              {acc > 0 ? `${acc}%` : '—'}
            </p>
            <p className="text-xs sm:text-sm text-[#445E54] leading-snug">AI forecast accuracy</p>
          </div>

          {/* 3 — Count-up: verified farmers (live from farmers table) */}
          <div style={stagger(2)} className="flex flex-col items-center gap-3 rounded-2xl bg-gradient-to-br from-[#EFF6FF] to-[#DBEAFE] border border-[#3B82F6]/20 p-5 text-center">
            <div className="relative w-11 h-11">
              {seen && (
                <span className="absolute inset-0 rounded-full bg-[#3B82F6]/25 animate-ping [animation-duration:1.8s]" />
              )}
              <div className="relative w-11 h-11 rounded-full bg-[#3B82F6]/20 flex items-center justify-center">
                <Users className="h-5 w-5 text-[#3B82F6]" />
              </div>
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-[#1D4ED8] tabular-nums leading-none">
              {farmersC.toLocaleString()}+
            </p>
            <p className="text-xs sm:text-sm text-[#565959] leading-snug">Verified farmers</p>
          </div>

          {/* 4 — Count-up + ripple: live markets (live from ghana_markets) */}
          <div style={stagger(3)} className="flex flex-col items-center gap-3 rounded-2xl bg-gradient-to-br from-[#FFF7ED] to-[#FFEDD5] border border-[#F97316]/20 p-5 text-center">
            <div className="relative w-11 h-11 flex items-center justify-center">
              {seen && [0, 1].map(i => (
                <span
                  key={i}
                  className="absolute rounded-full border-2 border-[#F97316]"
                  style={{ inset: 0, animation: `agri-ripple 2s ease-out ${i * 0.8}s infinite` }}
                />
              ))}
              <MapPin className="relative h-5 w-5 text-[#F97316]" />
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-[#9A3412] leading-none">
              {marketsC}
            </p>
            <p className="text-xs sm:text-sm text-[#565959] leading-snug">Live Ghana markets</p>
          </div>

          {/* 5 — Typewriter: match speed */}
          <div style={stagger(4)} className="flex flex-col items-center gap-3 rounded-2xl bg-gradient-to-br from-[#F8FAFC] to-[#F1F5F9] border border-[#CBD5E1]/50 p-5 text-center">
            <div className="w-11 h-11 rounded-full bg-amber-100 flex items-center justify-center">
              <Zap className="h-5 w-5 text-amber-600" />
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-[#0F1111] font-mono tabular-nums leading-none min-h-[2rem]">
              {tw}{!twDone && seen && <span className="animate-pulse text-amber-500">|</span>}
            </p>
            <p className="text-xs sm:text-sm text-[#565959] leading-snug">Average match time</p>
          </div>

          {/* 6 — Shimmer: zero fees */}
          <div style={stagger(5)} className="relative flex flex-col items-center gap-3 rounded-2xl bg-gradient-to-br from-[#F0FDF4] to-[#DCFCE7] border border-[#22C55E]/40 p-5 text-center overflow-hidden">
            {seen && (
              <div
                className="pointer-events-none absolute top-0 bottom-0 w-2/5 -skew-x-12 bg-gradient-to-r from-transparent via-white/60 to-transparent"
                style={{ animation: 'agri-shimmer 2.5s ease-in-out 0.8s 3' }}
              />
            )}
            <div className="relative w-11 h-11 rounded-full bg-[#22C55E]/20 flex items-center justify-center">
              <Gift className={`h-5 w-5 text-[#22C55E] ${seen ? 'animate-bounce' : ''}`} />
            </div>
            <p className="relative text-2xl sm:text-3xl font-bold text-[#131921] leading-none">Free</p>
            <p className="relative text-xs sm:text-sm text-[#565959] leading-snug">Zero buyer fees, always</p>
          </div>

        </div>
      </div>
    </section>
  )
}
