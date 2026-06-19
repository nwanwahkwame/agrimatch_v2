'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Search, MessageCircle, Menu, Leaf, X, LogOut, User } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { getAdminCrops, getAdminRegions } from '@/lib/api'

const REGION_EMOJIS: Record<string, string> = {
  'Ashanti': '🌿', 'Bono': '🌾', 'Bono East': '🌾', 'Northern': '🌻',
  'Eastern': '🍃', 'Greater Accra': '🏙️', 'Volta': '🌊', 'Upper East': '☀️',
  'Upper West': '☀️', 'North East': '🌻', 'Savannah': '🌵', 'Oti': '🌊',
  'Central': '🏖️', 'Western': '🌴', 'Western North': '🌴', 'Ahafo': '🌿',
}

export default function BuyerNav() {
  const [query, setQuery]       = useState('')
  const [category, setCategory] = useState('All')
  const [showAll, setShowAll] = useState(false)
  const [categories, setCategories] = useState<string[]>(['All'])
  const [regions, setRegions]   = useState<{ label: string; href: string; emoji: string }[]>([])
  const [interestCount, setInterestCount] = useState(0)
  const { user, logout } = useAuth()
  const router           = useRouter()

  useEffect(() => {
    const calcUnread = () => {
      const total = parseInt(localStorage.getItem('agrimatch_interests') || '0', 10)
      const seen  = parseInt(localStorage.getItem('agrimatch_seen')      || '0', 10)
      setInterestCount(Math.max(0, total - seen))
    }
    calcUnread()
    window.addEventListener('interest-added', calcUnread)
    window.addEventListener('cart-seen',      calcUnread)
    return () => {
      window.removeEventListener('interest-added', calcUnread)
      window.removeEventListener('cart-seen',      calcUnread)
    }
  }, [])

  useEffect(() => {
    getAdminCrops()
      .then(r => {
        const names = (r.data as { name: string }[])
          .filter(c => c && c.name)
          .map(c => c.name.replace(/_/g, ' ').replace(/^\w/, x => x.toUpperCase()))
        setCategories(['All', ...names])
      })
      .catch(() => {})
    getAdminRegions()
      .then(r => {
        const items = (r.data as { region: string }[]).map(r => ({
          label: r.region,
          href:  `/shop?region=${encodeURIComponent(r.region)}`,
          emoji: REGION_EMOJIS[r.region] ?? '🌍',
        }))
        items.push({ label: 'Byproducts', href: '/byproducts', emoji: '♻️' })
        items.push({ label: 'All Produce', href: '/shop', emoji: '🛒' })
        setRegions(items)
      })
      .catch(() => {})
  }, [])

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const crop = category === 'All' ? '' : category.toLowerCase()
    router.push(`/shop?q=${encodeURIComponent(query)}&crop=${crop}`)
  }

  return (
    <header className="sticky top-0 z-50 shadow-md">

      {/* ── Top bar ──────────────────────────────────────────────── */}
      <div className="bg-[#131921] px-3 py-2 flex items-center gap-2 sm:gap-3">

        {/* Logo */}
        <Link
          href="/"
          className="flex items-center gap-1 text-white border-2 border-transparent hover:border-[#22C55E] rounded px-1.5 py-0.5 shrink-0"
        >
          <Leaf className="h-5 w-5 text-[#22C55E]" strokeWidth={2.5} />
          <span className="font-bold text-base leading-none text-white">
            agri<span className="text-[#22C55E]">match</span>
          </span>
        </Link>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex flex-1 rounded overflow-hidden min-w-0">
          <select
            value={category}
            onChange={e => setCategory(e.target.value)}
            className="hidden sm:block bg-[#F3F3F3] hover:bg-[#E8E8E8] text-[#555] text-xs px-2 border-r border-gray-300 shrink-0 outline-none cursor-pointer"
          >
            {categories.map(c => <option key={c}>{c}</option>)}
          </select>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search crop, farmer or district..."
            className="flex-1 px-3 py-2 text-sm outline-none text-[#0F1111] bg-white min-w-0"
          />
          <button
            type="submit"
            className="bg-[#22C55E] hover:bg-[#4ADE80] px-4 flex items-center shrink-0 transition-colors"
          >
            <Search className="h-5 w-5 text-white" />
          </button>
        </form>

        {/* Account section */}
        {user ? (
          /* Logged-in: always-visible name + direct sign-out link */
          <div className="flex items-center gap-1 shrink-0">
            <div className="hidden md:flex flex-col text-left border-2 border-transparent rounded px-2 py-1">
              <span className="text-[10px] text-[#CCCCCC] leading-none">Hello, {user.name.split(' ')[0]}</span>
              <span className="text-sm font-bold text-white leading-none mt-0.5 capitalize">{user.role}</span>
            </div>
            {/* Mobile: just a user icon linking to dashboard/seller */}
            <a href={user.role === 'seller' ? '/seller' : user.role === 'admin' ? '/admin' : '/dashboard'}
              className="md:hidden flex items-center text-white border-2 border-transparent hover:border-[#22C55E] rounded px-2 py-1 transition-colors">
              <User className="h-5 w-5" />
            </a>
            {/* Sign out — always visible, plain link so it always works */}
            <a href="/api/auth/logout"
              className="flex items-center gap-1 text-red-400 hover:text-red-300 border-2 border-transparent hover:border-red-400/50 rounded px-2 py-1 transition-colors text-xs font-semibold whitespace-nowrap">
              <LogOut className="h-3.5 w-3.5 shrink-0" />
              <span className="hidden sm:inline">Sign out</span>
            </a>
          </div>
        ) : (
          /* Guest: direct links, no dropdown */
          <div className="flex items-center gap-1 shrink-0">
            <a
              href="/login"
              className="flex flex-col text-white border-2 border-transparent hover:border-[#22C55E] rounded px-2 py-1 transition-colors"
            >
              <span className="text-[10px] text-[#CCCCCC] leading-none hidden md:block">Hello, guest</span>
              <span className="text-sm font-bold leading-none flex items-center gap-1">
                <User className="h-4 w-4 md:hidden" />
                <span className="hidden md:inline">Sign in</span>
              </span>
            </a>
            <a
              href="/signup"
              className="hidden md:block bg-[#22C55E] hover:bg-[#16A34A] text-white text-xs font-bold px-3 py-1.5 rounded transition-colors whitespace-nowrap"
            >
              Register
            </a>
          </div>
        )}

        {/* Enquiries */}
        <Link
          href="/shop/cart"
          className="flex items-end gap-1 text-white border-2 border-transparent hover:border-[#22C55E] rounded px-2 py-0.5 shrink-0"
        >
          <div className="relative">
            <MessageCircle className="h-7 w-7" />
            {interestCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 bg-[#22C55E] text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-0.5 leading-none">
                {interestCount > 99 ? '99+' : interestCount}
              </span>
            )}
          </div>
          <span className="hidden sm:block text-sm font-bold pb-0.5">Enquiries</span>
        </Link>
      </div>

      {/* ── Secondary nav ─────────────────────────────────────────── */}
      <nav className="bg-[#232F3E] px-3 py-1.5 flex items-center gap-1 overflow-x-auto scrollbar-hide">
        <button
          onClick={() => setShowAll(v => !v)}
          className={`flex items-center gap-1.5 text-white text-sm font-bold whitespace-nowrap rounded px-2 py-1 shrink-0 transition-colors ${showAll ? 'bg-white/20' : 'hover:bg-white/10'}`}
        >
          {showAll ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />} All
        </button>
        {[
          { label: 'All Listings',        href: '/shop'           },
          { label: 'Market Prices',       href: '/market'         },
          { label: "Today's Best",        href: '/shop?view=best' },
          { label: 'Demand Board',        href: '/demand'         },
          { label: 'My Dashboard',        href: '/dashboard'      },
          { label: 'Byproducts',          href: '/byproducts'     },
          { label: 'Sell on AgriMatch',   href: '/seller'         },
          { label: 'Transport Provider',  href: '/transport'      },
        ].map(({ label, href }) => (
          <Link
            key={label}
            href={href}
            className="text-white text-sm whitespace-nowrap hover:bg-white/10 rounded px-2 py-1 shrink-0 border-2 border-transparent hover:border-white/30 transition-colors"
          >
            {label}
          </Link>
        ))}
      </nav>

      {/* ── All-menu dropdown ─────────────────────────────────────── */}
      {showAll && (
        <div className="bg-white border-t border-[#DDDDDD] shadow-lg px-4 py-5">
          <div className="mx-auto max-w-screen-xl">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[#999] mb-3">Browse by region</p>
            <div className="grid grid-cols-4 gap-2 sm:grid-cols-8">
              {regions.map(({ label, href, emoji }) => (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setShowAll(false)}
                  className="flex flex-col items-center gap-1.5 rounded-lg border border-[#EEEEEE] bg-[#FAFAFA] hover:border-[#22C55E]/60 hover:bg-[#F0FDF4] px-2 py-3 text-center transition-colors group"
                >
                  <span className="text-2xl">{emoji}</span>
                  <span className="text-xs font-medium text-[#0F1111] group-hover:text-[#15803D] leading-tight">{label}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
