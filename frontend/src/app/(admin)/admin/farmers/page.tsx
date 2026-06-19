'use client'

import { useState, useEffect } from 'react'
import { Users, UserCheck, FileText, Clock, CheckCircle, XCircle, RotateCcw, ShieldOff, RefreshCw } from 'lucide-react'
import { getAdminFarmers, updateFarmerStatus } from '@/lib/api'

type Status = 'active' | 'declined'

interface Farmer {
  id:           number
  name:         string
  phone:        string
  district:     string
  region:       string
  declarations: number
  status:       Status
  joined:       string | null
}

type Filter = 'all' | Status

function fmt(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

const STATUS_STYLES: Record<Status, string> = {
  active:   'bg-green-100 text-green-700',
  declined: 'bg-red-100   text-red-700',
}

interface Toast { id: number; msg: string; type: 'success' | 'error' | 'info' }

function Skel() {
  return (
    <tr>
      {[...Array(9)].map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded animate-pulse" />
        </td>
      ))}
    </tr>
  )
}

export default function AdminFarmersPage() {
  const [farmers,  setFarmers]  = useState<Farmer[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')
  const [filter,   setFilter]   = useState<Filter>('all')
  const [toasts,   setToasts]   = useState<Toast[]>([])

  function load() {
    setLoading(true); setError('')
    getAdminFarmers()
      .then(r => setFarmers(r.data as Farmer[]))
      .catch(() => setError('Could not load farmers from the database.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const counts = {
    all:      farmers.length,
    active:   farmers.filter(f => f.status === 'active').length,
    declined: farmers.filter(f => f.status === 'declined').length,
  }
  const totalDeclarations = farmers.reduce((s, f) => s + f.declarations, 0)
  const displayed = filter === 'all' ? farmers : farmers.filter(f => f.status === filter)

  function pushToast(msg: string, type: Toast['type'] = 'success') {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500)
  }

  async function setStatus(id: number, action: 'approve' | 'decline') {
    const name = farmers.find(f => f.id === id)?.name ?? 'Farmer'
    try {
      await updateFarmerStatus(id, action)
      setFarmers(prev =>
        prev.map(f => f.id === id
          ? { ...f, status: action === 'approve' ? 'active' : 'declined' }
          : f
        )
      )
      if (action === 'approve') pushToast(`${name} approved and activated.`, 'success')
      else                       pushToast(`${name} suspended.`, 'error')
    } catch {
      pushToast('Action failed — please try again.', 'error')
    }
  }

  return (
    <div className="p-6 max-w-screen-xl mx-auto">

      {/* Toast stack */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map(t => (
          <div key={t.id} className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white ${
            t.type === 'success' ? 'bg-[#16A34A]' : t.type === 'error' ? 'bg-red-600' : 'bg-[#2563EB]'
          }`}>
            {t.type === 'success' ? <CheckCircle className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
            {t.msg}
          </div>
        ))}
      </div>

      {/* Heading */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#0F1111] mb-1">Farmers</h1>
          <p className="text-sm text-[#565959]">Registered farmers — live from database</p>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-2 border border-[#DDDDDD] bg-white hover:bg-[#F0FDF4] text-sm px-3 py-2 rounded transition-colors disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 border border-red-200 bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Farmers',      value: counts.all,          icon: Users,      color: '#1D6B3A' },
          { label: 'Active',             value: counts.active,        icon: UserCheck,  color: '#16A34A' },
          { label: 'Suspended',          value: counts.declined,      icon: Clock,      color: '#D97706' },
          { label: 'Total Declarations', value: totalDeclarations,    icon: FileText,   color: '#2563EB' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-lg border border-[#DDDDDD] p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
              style={{ backgroundColor: `${color}18` }}>
              <Icon className="h-5 w-5" style={{ color }} />
            </div>
            <div>
              <p className="text-2xl font-bold text-[#0F1111]">{loading ? '…' : value}</p>
              <p className="text-xs text-[#565959] leading-tight">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">

        {/* Filter tabs */}
        <div className="flex border-b border-[#EEEEEE] px-4 pt-3 gap-1 overflow-x-auto">
          {([
            { key: 'all',      label: 'All',       count: counts.all      },
            { key: 'active',   label: 'Active',    count: counts.active   },
            { key: 'declined', label: 'Suspended', count: counts.declined },
          ] as { key: Filter; label: string; count: number }[]).map(tab => (
            <button key={tab.key} onClick={() => setFilter(tab.key)}
              className={`flex items-center gap-1.5 px-3 pb-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                filter === tab.key
                  ? 'border-[#22C55E] text-[#22C55E]'
                  : 'border-transparent text-[#565959] hover:text-[#0F1111]'
              }`}>
              {tab.label}
              <span className={`text-xs rounded-full px-1.5 py-0.5 ${
                filter === tab.key ? 'bg-[#22C55E]/10 text-[#22C55E]' : 'bg-[#F3F3F3] text-[#565959]'
              }`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F7F7F7] text-xs text-[#565959] uppercase tracking-wide">
              <tr>
                {['ID', 'Name', 'Phone', 'District', 'Region', 'Declarations', 'Joined', 'Status', 'Actions'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left font-semibold whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EEEEEE]">
              {loading ? (
                [...Array(5)].map((_, i) => <Skel key={i} />)
              ) : displayed.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-sm text-[#565959]">
                    No farmers in this category.
                  </td>
                </tr>
              ) : displayed.map(f => (
                <tr key={f.id} className="hover:bg-[#FAFAFA]">
                  <td className="px-4 py-3 text-[#565959] font-mono text-xs">#{f.id}</td>
                  <td className="px-4 py-3 font-medium text-[#0F1111] whitespace-nowrap">{f.name}</td>
                  <td className="px-4 py-3 text-[#565959] whitespace-nowrap">{f.phone}</td>
                  <td className="px-4 py-3 text-[#565959]">{f.district}</td>
                  <td className="px-4 py-3 text-[#565959] whitespace-nowrap">{f.region}</td>
                  <td className="px-4 py-3 text-center font-semibold text-[#0F1111]">{f.declarations}</td>
                  <td className="px-4 py-3 text-[#565959] whitespace-nowrap">{fmt(f.joined)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_STYLES[f.status]}`}>
                      {f.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      {f.status === 'active' ? (
                        <button onClick={() => setStatus(f.id, 'decline')} title="Suspend"
                          className="p-1.5 rounded bg-gray-100 hover:bg-red-100 text-gray-500 hover:text-red-600 transition-colors">
                          <ShieldOff className="h-4 w-4" />
                        </button>
                      ) : (
                        <button onClick={() => setStatus(f.id, 'approve')} title="Reinstate"
                          className="p-1.5 rounded bg-blue-100 hover:bg-blue-200 text-blue-600 transition-colors">
                          <RotateCcw className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
