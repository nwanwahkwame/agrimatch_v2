'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { clsx } from 'clsx'
import {
  LayoutDashboard,
  ListOrdered,
  TrendingUp,
  Lightbulb,
  Bell,
  Search,
  BarChart2,
  Package,
  ShoppingBag,
  Users,
  MapPin,
  Database,
  Cpu,
} from 'lucide-react'
import type { Role } from './Navbar'

interface SidebarProps {
  role: Role
}

const NAV: Record<Role, { href: string; label: string; icon: React.ReactNode }[]> = {
  farmer: [
    { href: '/farmer/listings',       label: 'My Listings',      icon: <ListOrdered   className="h-4 w-4" /> },
    { href: '/farmer/forecasts',      label: 'Price Forecasts',  icon: <TrendingUp    className="h-4 w-4" /> },
    { href: '/farmer/recommendations',label: 'Recommendations',  icon: <Lightbulb     className="h-4 w-4" /> },
    { href: '/farmer/alerts',         label: 'Alerts',           icon: <Bell          className="h-4 w-4" /> },
  ],
  buyer: [
    { href: '/buyer/find',            label: 'Find Produce',     icon: <Search        className="h-4 w-4" /> },
    { href: '/buyer/charts',          label: 'Price Charts',     icon: <BarChart2     className="h-4 w-4" /> },
    { href: '/buyer/byproducts',      label: 'Byproduct Market', icon: <Package       className="h-4 w-4" /> },
    { href: '/buyer/orders',          label: 'My Orders',        icon: <ShoppingBag   className="h-4 w-4" /> },
  ],
  admin: [
    { href: '/admin',                 label: 'Dashboard',        icon: <LayoutDashboard className="h-4 w-4" /> },
    { href: '/admin/farmers',         label: 'Farmers',          icon: <Users         className="h-4 w-4" /> },
    { href: '/admin/markets',         label: 'Markets',          icon: <MapPin        className="h-4 w-4" /> },
    { href: '/admin/pipeline',        label: 'Data Pipeline',    icon: <Database      className="h-4 w-4" /> },
    { href: '/admin/models',          label: 'Models',           icon: <Cpu           className="h-4 w-4" /> },
  ],
}

export default function Sidebar({ role }: SidebarProps) {
  const pathname = usePathname()
  const links = NAV[role]

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-[#C8D8D2] bg-[#F7FAF8] py-6">
      <nav className="flex flex-col gap-1 px-3">
        {links.map(({ href, label, icon }) => {
          const active = pathname === href || pathname.startsWith(href + '/')
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                active
                  ? 'bg-[#E8F5EE] text-[#1D6B3A]'
                  : 'text-[#445E54] hover:bg-[#EEF4F1] hover:text-[#1D6B3A]',
              )}
            >
              <span className={active ? 'text-[#1D6B3A]' : 'text-[#7A9088]'}>{icon}</span>
              {label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
