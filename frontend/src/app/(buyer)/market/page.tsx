'use client'

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { TrendingUp, TrendingDown, Minus, Clock, Search, ChevronDown } from 'lucide-react'
import API from '@/lib/api'
import type { BulletinEntry } from '@/types/api'

// ─── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function cropLabel(name: string) {
  return name.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

function trendBadge(pct: number | null): { label: string; cls: string } {
  if (pct === null) return { label: 'No data', cls: 'bg-gray-100 text-gray-500' }
  if (pct >= 10)    return { label: 'Surging',  cls: 'bg-green-100 text-green-700' }
  if (pct >= 3)     return { label: 'Rising',   cls: 'bg-emerald-100 text-emerald-700' }
  if (pct > -3)     return { label: 'Stable',   cls: 'bg-blue-100 text-blue-700' }
  if (pct > -10)    return { label: 'Falling',  cls: 'bg-orange-100 text-orange-700' }
  return              { label: 'Dropping',  cls: 'bg-red-100 text-red-700' }
}

// ─── Skeleton ──────────────────────────────────────────────────────────────────

function TableSkel() {
  return (
    <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden animate-pulse">
      <div className="h-10 bg-[#F0FDF4] border-b border-[#DDDDDD]" />
      <div className="divide-y divide-[#EEEEEE]">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex gap-4 px-4 py-3">
            <div className="h-4 bg-gray-200 rounded w-32" />
            <div className="h-4 bg-gray-200 rounded w-20" />
            <div className="h-4 bg-gray-200 rounded w-16 ml-auto" />
            <div className="h-4 bg-gray-200 rounded w-16" />
            <div className="h-4 bg-gray-200 rounded w-16" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Change cell ───────────────────────────────────────────────────────────────

function ChangeCell({ pct }: { pct: number | null }) {
  if (pct === null) {
    return <span className="text-[#999]"><Minus className="inline h-3.5 w-3.5" /></span>
  }
  const up  = pct > 0
  const eq  = pct === 0
  return (
    <span className={`flex items-center gap-0.5 font-semibold text-sm ${up ? 'text-[#22C55E]' : eq ? 'text-[#565959]' : 'text-red-500'}`}>
      {up  ? <TrendingUp   className="h-3.5 w-3.5 shrink-0" /> :
       eq  ? <Minus        className="h-3.5 w-3.5 shrink-0" /> :
             <TrendingDown className="h-3.5 w-3.5 shrink-0" />}
      {Math.abs(pct).toFixed(1)}%
    </span>
  )
}

// ─── Crop section ─────────────────────────────────────────────────────────────

function CropSection({ crop, rows }: { crop: string; rows: BulletinEntry[] }) {
  const avgPrice = rows.reduce((s, r) => s + r.latest_price, 0) / rows.length
  const bestRow  = rows.reduce((best, r) => r.latest_price > best.latest_price ? r : best, rows[0])

  return (
    <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-[#F0FDF4] border-b border-[#DDDDDD]">
        <div className="flex items-center gap-3">
          <span className="text-base font-bold text-[#1D6B3A] capitalize">{cropLabel(crop)}</span>
          <span className="text-xs text-[#565959]">{rows.length} market{rows.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-[#565959]">
          <span>Avg: <strong className="text-[#0F1111]">GHS {avgPrice.toFixed(2)}/kg</strong></span>
          <span className="hidden sm:inline">Best: <strong className="text-[#22C55E]">{bestRow.market} @ GHS {bestRow.latest_price.toFixed(2)}</strong></span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#F7F7F7] border-b border-[#EEEEEE] text-xs text-[#565959] uppercase tracking-wide">
              <th className="px-4 py-2.5 text-left font-semibold">Market</th>
              <th className="px-4 py-2.5 text-left font-semibold">Region</th>
              <th className="px-4 py-2.5 text-right font-semibold">Price (GHS/kg)</th>
              <th className="px-4 py-2.5 text-right font-semibold">Date</th>
              <th className="px-4 py-2.5 text-right font-semibold">30-day change</th>
              <th className="px-4 py-2.5 text-right font-semibold">Trend</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EEEEEE]">
            {rows.map((row, i) => {
              const badge = trendBadge(row.change_pct)
              return (
                <tr key={`${row.market}-${i}`} className="hover:bg-[#FAFAFA] transition-colors">
                  <td className="px-4 py-3 font-medium text-[#0F1111] whitespace-nowrap">{row.market}</td>
                  <td className="px-4 py-3 text-[#565959] whitespace-nowrap">{row.region}</td>
                  <td className="px-4 py-3 text-right font-bold text-[#0F1111]">
                    {row.latest_price.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right text-[#565959] whitespace-nowrap text-xs">
                    {fmtDate(row.latest_date)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ChangeCell pct={row.change_pct} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${badge.cls}`}>
                      {badge.label}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ onClear }: { onClear: () => void }) {
  return (
    <div className="bg-white rounded-lg border border-[#DDDDDD] p-12 text-center">
      <Search className="mx-auto h-10 w-10 text-gray-300 mb-3" />
      <p className="font-semibold text-[#0F1111] mb-1">No prices match your filters</p>
      <p className="text-sm text-[#565959] mb-4">
        Try selecting a different crop or region, or clear all filters.
      </p>
      <button onClick={onClear} className="text-sm text-[#007185] hover:underline font-semibold">
        Clear filters
      </button>
    </div>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function MarketBulletinPage() {
  const [cropFilter, setCropFilter] = useState('all')
  const [regFilter,  setRegFilter]  = useState('all')

  const { data: rows = [], isLoading, error } = useQuery<BulletinEntry[]>({
    queryKey: ['market-bulletin'],
    queryFn:  () => API.get('/api/market-bulletin').then(r => r.data ?? []),
    staleTime: 5 * 60_000,  // prices are fresh for 5 minutes
  })

  const crops   = useMemo(() => ['all', ...[...new Set(rows.map(r => r.crop))].sort()],   [rows])
  const regions = useMemo(() => ['all', ...[...new Set(rows.map(r => r.region))].sort()], [rows])

  const lastUpdated = useMemo(() => {
    if (!rows.length) return null
    const latest = rows.reduce((best, r) =>
      new Date(r.latest_date) > new Date(best) ? r.latest_date : best
    , rows[0].latest_date)
    return fmtDate(latest)
  }, [rows])

  const grouped = useMemo(() => {
    const filtered = rows.filter(r => {
      if (cropFilter !== 'all' && r.crop !== cropFilter) return false
      if (regFilter  !== 'all' && r.region !== regFilter) return false
      return true
    })
    const map: Record<string, BulletinEntry[]> = {}
    filtered.forEach(r => {
      if (!map[r.crop]) map[r.crop] = []
      map[r.crop].push(r)
    })
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b))
  }, [rows, cropFilter, regFilter])

  function clearFilters() {
    setCropFilter('all')
    setRegFilter('all')
  }

  return (
    <div className="mx-auto max-w-screen-xl px-4 py-6 pb-20">

      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-[#0F1111]">Market Prices</h1>
          <p className="text-sm text-[#565959] mt-0.5">Live commodity prices across Ghana</p>
        </div>
        {lastUpdated && !isLoading && (
          <div className="flex items-center gap-1.5 text-xs text-[#565959] shrink-0">
            <Clock className="h-3.5 w-3.5 text-[#22C55E]" />
            Last updated: <strong className="text-[#0F1111]">{lastUpdated}</strong>
          </div>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 mb-6 bg-white border border-[#DDDDDD] rounded-lg px-4 py-3 items-center">
        <span className="text-xs font-semibold text-[#565959] uppercase tracking-wide">Filter by:</span>

        <div className="relative">
          <select
            value={cropFilter}
            onChange={e => setCropFilter(e.target.value)}
            className="appearance-none border border-[#DDDDDD] rounded bg-white pl-3 pr-8 py-1.5 text-sm text-[#0F1111] outline-none focus:border-[#22C55E] cursor-pointer"
          >
            <option value="all">All Crops</option>
            {crops.filter(c => c !== 'all').map(c => (
              <option key={c} value={c}>{cropLabel(c)}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#565959] pointer-events-none" />
        </div>

        <div className="relative">
          <select
            value={regFilter}
            onChange={e => setRegFilter(e.target.value)}
            className="appearance-none border border-[#DDDDDD] rounded bg-white pl-3 pr-8 py-1.5 text-sm text-[#0F1111] outline-none focus:border-[#22C55E] cursor-pointer"
          >
            <option value="all">All Regions</option>
            {regions.filter(r => r !== 'all').map(r => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#565959] pointer-events-none" />
        </div>

        {(cropFilter !== 'all' || regFilter !== 'all') && (
          <button
            onClick={clearFilters}
            className="text-xs text-[#007185] hover:text-[#15803D] hover:underline font-medium ml-1"
          >
            Clear filters
          </button>
        )}

        {!isLoading && (
          <span className="ml-auto text-xs text-[#565959]">
            {grouped.reduce((s, [, rs]) => s + rs.length, 0)} price
            {grouped.reduce((s, [, rs]) => s + rs.length, 0) !== 1 ? 's' : ''} across{' '}
            {grouped.length} crop{grouped.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 mb-5">
          Could not load market prices. Please try again.
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="flex flex-col gap-5">
          {[...Array(3)].map((_, i) => <TableSkel key={i} />)}
        </div>
      ) : grouped.length === 0 ? (
        <EmptyState onClear={clearFilters} />
      ) : (
        <div className="flex flex-col gap-5">
          {grouped.map(([crop, cropRows]) => (
            <CropSection key={crop} crop={crop} rows={cropRows} />
          ))}
        </div>
      )}
    </div>
  )
}
