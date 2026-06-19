'use client'

import { Leaf } from 'lucide-react'
import { clsx } from 'clsx'

export type Role = 'farmer' | 'buyer' | 'admin'

interface NavbarProps {
  role: Role
  onRoleChange: (role: Role) => void
  phoneNumber?: string
}

const ROLES: { key: Role; label: string }[] = [
  { key: 'farmer', label: 'Farmer' },
  { key: 'buyer',  label: 'Buyer'  },
  { key: 'admin',  label: 'Admin'  },
]

export default function Navbar({ role, onRoleChange, phoneNumber }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#C8D8D2] bg-[#145228]">
      <div className="mx-auto flex h-14 max-w-screen-xl items-center justify-between px-4">

        {/* Logo */}
        <div className="flex items-center gap-2">
          <Leaf className="h-5 w-5 text-[#4DB876]" strokeWidth={2.5} />
          <span className="font-display text-lg font-semibold tracking-tight text-white">
            AgriMatch
          </span>
        </div>

        {/* Role switcher */}
        <nav className="flex items-center rounded-full bg-[#0D3D20] p-1 gap-1">
          {ROLES.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => onRoleChange(key)}
              className={clsx(
                'rounded-full px-4 py-1.5 text-sm font-medium transition-all duration-150',
                role === key
                  ? 'bg-[#2EA05A] text-white shadow-sm'
                  : 'text-[#7DCFA0] hover:text-white',
              )}
            >
              {label}
            </button>
          ))}
        </nav>

        {/* Phone number */}
        <div className="text-sm text-[#7DCFA0]">
          {phoneNumber ?? ''}
        </div>

      </div>
    </header>
  )
}
