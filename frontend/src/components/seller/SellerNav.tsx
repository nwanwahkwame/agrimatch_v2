'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Package, PlusCircle, BarChart2,
  Recycle, User, ExternalLink, Leaf, LogOut, CalendarDays, Calculator,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

const NAV = [
  { href: '/seller',           icon: LayoutDashboard, label: 'Dashboard'         },
  { href: '/seller/listings',  icon: Package,         label: 'Inventory'         },
  { href: '/seller/new',       icon: PlusCircle,      label: 'Add Listing'       },
  { href: '/seller/analytics', icon: BarChart2,       label: 'Analytics'         },
  { href: '/seller/planting',  icon: CalendarDays,    label: 'Planting Calendar' },
  { href: '/seller/roi',       icon: Calculator,      label: 'ROI Calculator'    },
  { href: '/byproducts',       icon: Recycle,         label: 'Byproducts'        },
  { href: '/seller/account',   icon: User,            label: 'Account'           },
]

export default function SellerNav() {
  const pathname    = usePathname()
  const { user, logout } = useAuth()

  return (
    <>
      {/* ── Desktop sidebar ──────────────────────────────────────── */}
      <aside className="hidden md:flex w-56 shrink-0 bg-[#232F3E] min-h-screen flex-col">

        {/* Logo */}
        <div className="px-4 py-4 border-b border-white/10">
          <Link href="/seller" className="flex items-center gap-2">
            <Leaf className="h-5 w-5 text-[#22C55E]" />
            <div>
              <p className="text-white font-bold text-sm leading-none">AgriMatch</p>
              <p className="text-[#22C55E] text-[10px] font-semibold leading-none mt-0.5">Seller Central</p>
            </div>
          </Link>
        </div>

        {/* User info */}
        {user && (
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white text-xs font-semibold truncate">{user.name}</p>
            <p className="text-[#AAAAAA] text-[10px] mt-0.5">
              {user.farmerId ?? user.phone ?? user.email ?? 'Farmer'}
            </p>
          </div>
        )}

        {/* Nav items */}
        <nav className="flex-1 py-4 flex flex-col gap-0.5">
          {NAV.map(({ href, icon: Icon, label }) => {
            const active = pathname === href || (href !== '/seller' && pathname.startsWith(href))
            return (
              <Link key={href} href={href}
                className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  active
                    ? 'bg-[#37475A] text-white font-semibold border-l-4 border-[#22C55E]'
                    : 'text-[#CCCCCC] hover:bg-[#37475A] hover:text-white border-l-4 border-transparent'
                }`}>
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-4 py-4 border-t border-white/10 flex flex-col gap-2">
          <Link href="/"
            className="flex items-center gap-2 text-xs text-[#AAAAAA] hover:text-white transition-colors">
            <ExternalLink className="h-3.5 w-3.5" /> Buyer Marketplace
          </Link>
          <button onClick={logout}
            className="flex items-center gap-2 text-xs text-red-400 hover:text-red-300 transition-colors">
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
      </aside>

      {/* ── Mobile bottom tab bar ─────────────────────────────────── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-[#232F3E] border-t border-white/10 flex">
        {NAV.slice(0, 4).map(({ href, icon: Icon, label }) => {
          const active = pathname === href || (href !== '/seller' && pathname.startsWith(href))
          return (
            <Link key={href} href={href}
              className={`flex-1 flex flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors ${
                active ? 'text-[#22C55E]' : 'text-[#AAAAAA]'
              }`}>
              <Icon className="h-5 w-5" />
              <span className="leading-none">{label.split(' ')[0]}</span>
            </Link>
          )
        })}
      </nav>
    </>
  )
}
