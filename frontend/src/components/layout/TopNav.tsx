'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Leaf } from 'lucide-react'
import { clsx } from 'clsx'

const LINKS = [
  { href: '/farmer',     label: 'Farmer Dashboard'   },
  { href: '/buyer',      label: 'Buyer Marketplace'  },
  { href: '/byproducts', label: 'Byproduct Market'   },
]

export default function TopNav() {
  const pathname = usePathname()

  return (
    <nav className="sticky top-0 z-40 w-full border-b border-[#C8D8D2] bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="mx-auto flex h-12 max-w-screen-xl items-center gap-6 px-4">
        <Link href="/" className="flex items-center gap-1.5 shrink-0">
          <Leaf className="h-4 w-4 text-[#1D6B3A]" strokeWidth={2.5} />
          <span className="font-display text-sm font-bold text-[#1D6B3A]">AgriMatch</span>
        </Link>
        <div className="h-4 w-px bg-[#C8D8D2]" />
        <div className="flex items-center gap-1">
          {LINKS.map(({ href, label }) => {
            const active = pathname === href || pathname.startsWith(href + '/')
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                  active
                    ? 'bg-[#E8F5EE] text-[#1D6B3A]'
                    : 'text-[#445E54] hover:bg-[#EEF4F1] hover:text-[#1D6B3A]',
                )}
              >
                {label}
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
