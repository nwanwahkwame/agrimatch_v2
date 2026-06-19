'use client'

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { Session, getSession, clearSession } from '@/lib/auth'
import API from '@/lib/api'

interface AuthContextType {
  user:    Session | null
  loading: boolean
  logout:  () => Promise<void>
  refresh: () => void
}

const AuthContext = createContext<AuthContextType>({
  user: null, loading: true, logout: async () => {}, refresh: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(() => {
    setUser(getSession())
    setLoading(false)
  }, [])

  const logout = useCallback(async () => {
    await fetch('/api/auth/logout', { method: 'POST' })
    clearSession()
    setUser(null)
    window.location.href = '/login'
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // Auto-logout when the backend returns 401 (expired session) while user is active.
  useEffect(() => {
    const id = API.interceptors.response.use(
      r => r,
      err => {
        if (err.response?.status === 401 && user) logout()
        return Promise.reject(err)
      },
    )
    return () => API.interceptors.response.eject(id)
  }, [user, logout])

  return (
    <AuthContext.Provider value={{ user, loading, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
