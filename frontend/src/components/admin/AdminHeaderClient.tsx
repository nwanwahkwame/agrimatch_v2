'use client'

import { LogOut } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

export default function AdminHeaderClient() {
  const { user, logout } = useAuth()
  if (!user) return null

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-[#7DCFA0]">
        Signed in as <span className="text-white font-semibold">{user.name}</span>
      </span>
      <button
        onClick={logout}
        className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 transition-colors"
      >
        <LogOut className="h-3.5 w-3.5" /> Sign out
      </button>
    </div>
  )
}
