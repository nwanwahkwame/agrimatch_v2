'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, Users, MapPin, Activity, Brain, PhoneCall } from 'lucide-react'

const NAV = [
  { href: '/admin',           icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/admin/farmers',   icon: Users,           label: 'Farmers'   },
  { href: '/admin/markets',   icon: MapPin,          label: 'Markets'   },
  { href: '/admin/pipeline',  icon: Activity,        label: 'Pipeline'  },
  { href: '/admin/models',    icon: Brain,           label: 'AI Models' },
  { href: '/admin/ussd-test', icon: PhoneCall,       label: 'USSD Test' },
]

export default function AdminNav() {
  const pathname = usePathname()
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-48 shrink-0 bg-[#0F2D1A] min-h-full flex-col py-4">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = href === '/admin' ? pathname === href : pathname.startsWith(href)
          return (
            <Link key={href} href={href}
              className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors border-l-4 ${
                active
                  ? 'bg-[#1D6B3A] text-white font-semibold border-[#4DB876]'
                  : 'text-[#7DCFA0] hover:bg-[#1A3D22] hover:text-white border-transparent'
              }`}>
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          )
        })}
      </aside>

      {/* Mobile top tabs */}
      <nav className="md:hidden flex overflow-x-auto bg-[#0F2D1A] px-2 py-1 gap-1">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = href === '/admin' ? pathname === href : pathname.startsWith(href)
          return (
            <Link key={href} href={href}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs whitespace-nowrap shrink-0 transition-colors ${
                active ? 'bg-[#1D6B3A] text-white font-semibold' : 'text-[#7DCFA0]'
              }`}>
              <Icon className="h-3.5 w-3.5" />{label}
            </Link>
          )
        })}
      </nav>
    </>
  )
}
