'use client'

import { useState, useEffect } from 'react'
import { MapPin, TrendingUp, BarChart2, RefreshCw, Star } from 'lucide-react'
import { getAdminMarkets } from '@/lib/api'

interface Market {
  id:           number
  name:         string
  canonical:    string
  region:       string
  district:     string
  is_major_hub: boolean
  crops_tracked: number
  last_updated: string | null
  status:       'live' | 'stale'
}

function fmt(d: string | null) {
  if (!d) return 'No data'
  return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function Skel() {
  return (
    <tr>
      {[...Array(7)].map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded animate-pulse" />
        </td>
      ))}
    </tr>
  )
}

export default function AdminMarketsPage() {
  const [markets, setMarkets]   = useState<Market[]>([])
  const [loading, setLoading]   = useState(true)
  const [error,   setError]     = useState('')
  const [region,  setRegion]    = useState('All')

  function load() {
    setLoading(true); setError('')
    getAdminMarkets()
      .then(r => setMarkets(r.data as Market[]))
      .catch(() => setError('Could not load markets from the database.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const regions = ['All', ...Array.from(new Set(markets.map(m => m.region))).sort()]
  const displayed = region === 'All' ? markets : markets.filter(m => m.region === region)

  const liveCount  = markets.filter(m => m.status === 'live').length
  const staleCount = markets.filter(m => m.status === 'stale').length
  const hubCount   = markets.filter(m => m.is_major_hub).length

  return (
    <div className="p-6 max-w-screen-xl mx-auto">

      {/* Heading */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#0F1111] mb-1">Markets</h1>
          <p className="text-sm text-[#565959]">All tracked markets — live from database</p>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-2 border border-[#DDDDDD] bg-white hover:bg-[#F0FDF4] text-sm px-3 py-2 rounded transition-colors disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {error && (
        <div className="mb-6 border border-red-200 bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Markets',  value: loading ? '…' : markets.length, icon: MapPin,    color: '#1D6B3A' },
          { label: 'Live',           value: loading ? '…' : liveCount,       icon: TrendingUp, color: '#16A34A' },
          { label: 'Stale / Offline',value: loading ? '…' : staleCount,      icon: BarChart2,  color: '#D97706' },
          { label: 'Major Hubs',     value: loading ? '…' : hubCount,        icon: Star,       color: '#2563EB' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-lg border border-[#DDDDDD] p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
              style={{ backgroundColor: `${color}18` }}>
              <Icon className="h-5 w-5" style={{ color }} />
            </div>
            <div>
              <p className="text-2xl font-bold text-[#0F1111]">{value}</p>
              <p className="text-xs text-[#565959] leading-tight">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Region filter */}
      <div className="flex flex-wrap gap-2 mb-4">
        {regions.map(r => (
          <button key={r} onClick={() => setRegion(r)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              region === r
                ? 'bg-[#22C55E] text-white border-[#22C55E]'
                : 'bg-white text-[#565959] border-[#DDDDDD] hover:border-[#22C55E]'
            }`}>
            {r} {r !== 'All' && `(${markets.filter(m => m.region === r).length})`}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
        <div className="px-4 py-3 border-b border-[#EEEEEE] text-sm font-semibold text-[#0F1111]">
          {loading ? 'Loading…' : `${displayed.length} market${displayed.length !== 1 ? 's' : ''}`}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F7F7F7] text-xs text-[#565959] uppercase tracking-wide">
              <tr>
                {['Market', 'District', 'Region', 'Hub', 'Crops tracked', 'Last updated', 'Status'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left font-semibold whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EEEEEE]">
              {loading ? (
                [...Array(8)].map((_, i) => <Skel key={i} />)
              ) : displayed.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-[#565959]">
                    No markets found.
                  </td>
                </tr>
              ) : displayed.map(m => (
                <tr key={m.id} className="hover:bg-[#FAFAFA]">
                  <td className="px-4 py-3 font-medium text-[#0F1111] whitespace-nowrap">{m.name}</td>
                  <td className="px-4 py-3 text-[#565959]">{m.district}</td>
                  <td className="px-4 py-3 text-[#565959] whitespace-nowrap">{m.region}</td>
                  <td className="px-4 py-3">
                    {m.is_major_hub && (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                        <Star className="h-3 w-3" /> Hub
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center font-semibold text-[#0F1111]">{m.crops_tracked}</td>
                  <td className="px-4 py-3 text-[#565959] whitespace-nowrap">{fmt(m.last_updated)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      m.status === 'live' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {m.status}
                    </span>
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
