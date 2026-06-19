'use client'

import { useEffect, useState } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { TrendingUp, Package, DollarSign, BarChart2, Loader2 } from 'lucide-react'
import { getDeclarations } from '@/lib/api'
import API from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { farmerDbId } from '@/lib/auth'

interface Declaration {
  id:                  number
  crop:                string
  quantity_kg:         number
  harvest_date:        string
  status:              string
  price_forecast_ghs:  number | null
}

interface BulletinRow {
  crop:         string
  market:       string
  latest_price: number
}

// Derive monthly income buckets from declarations
function buildMonthly(decls: Declaration[]) {
  const map: Record<string, { income: number; declarations: number }> = {}
  decls.forEach(d => {
    const m = new Date(d.harvest_date).toLocaleString('en-GB', { month: 'short', year: '2-digit' })
    if (!map[m]) map[m] = { income: 0, declarations: 0 }
    map[m].income       += d.quantity_kg * (d.price_forecast_ghs ?? 0)
    map[m].declarations += 1
  })
  return Object.entries(map)
    .sort(([a], [b]) => new Date('01 ' + a).getTime() - new Date('01 ' + b).getTime())
    .slice(-6)
    .map(([month, v]) => ({ month, income: Math.round(v.income), declarations: v.declarations }))
}

export default function SellerAnalyticsPage() {
  const { user }              = useAuth()
  const farmerId              = farmerDbId(user)
  const [decls,    setDecls]    = useState<Declaration[]>([])
  const [bulletin, setBulletin] = useState<BulletinRow[]>([])
  const [history,  setHistory]  = useState<{ month: string; avg_price: number }[]>([])
  const [histCrop, setHistCrop] = useState('')
  const [loading,  setLoading]  = useState(true)
  const [hLoading, setHLoading] = useState(false)

  // Load declarations
  useEffect(() => {
    let alive = true
    setLoading(true)
    getDeclarations(farmerId)
      .then(r => { if (alive) setDecls(r.data ?? []) })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [farmerId])

  // Once we know which crops, load market bulletin + price history
  useEffect(() => {
    if (!decls.length) return
    const crops = new Set(decls.map(d => d.crop))
    const firstCrop = [...crops][0]
    setHistCrop(firstCrop)

    // Market bulletin — filter to this farmer's crops
    API.get('/api/market-bulletin')
      .then(r => {
        const rows = (r.data as BulletinRow[]).filter(row => crops.has(row.crop))
        setBulletin(rows)
      })
      .catch(() => {})

    // Historical price trend for first crop
    if (firstCrop) {
      setHLoading(true)
      API.get(`/api/prices/history/${firstCrop}?months=18`)
        .then(r => {
          const rows = r.data as { month: string; market: string; avg_price: number }[]
          const byMonth: Record<string, number[]> = {}
          rows.forEach(row => {
            if (!byMonth[row.month]) byMonth[row.month] = []
            byMonth[row.month].push(row.avg_price)
          })
          const series = Object.entries(byMonth)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([month, vals]) => ({
              month: new Date(month).toLocaleString('en-GB', { month: 'short', year: '2-digit' }),
              avg_price: parseFloat((vals.reduce((s, v) => s + v, 0) / vals.length).toFixed(2)),
            }))
          setHistory(series)
        })
        .catch(() => {})
        .finally(() => setHLoading(false))
    }
  }, [decls])

  // Derived stats from real declarations
  const totalIncome  = decls.reduce((s, d) => s + d.quantity_kg * (d.price_forecast_ghs ?? 0), 0)
  const activeDecls  = loading ? '-' : `${decls.filter(d => d.status === 'active').length}`
  const totalQty     = loading ? '-' : decls.reduce((s, d) => s + d.quantity_kg, 0).toLocaleString()
  const avgPrice     = (() => {
    const withPrice = decls.filter(d => d.price_forecast_ghs)
    if (!withPrice.length) return '-'
    return (withPrice.reduce((s, d) => s + (d.price_forecast_ghs ?? 0), 0) / withPrice.length).toFixed(2)
  })()

  const monthly = buildMonthly(decls)

  // Build price-by-market chart: rows = markets, columns = crops
  const farmerCrops = [...new Set(decls.map(d => d.crop))]
  const marketNames = [...new Set(bulletin.map(r => r.market))].slice(0, 8)
  const priceChart  = marketNames.map(market => {
    const row: Record<string, string | number> = { market }
    farmerCrops.forEach(crop => {
      const entry = bulletin.find(b => b.market === market && b.crop === crop)
      if (entry) row[crop] = parseFloat(entry.latest_price.toFixed(2))
    })
    return row
  })

  const CROP_COLORS: Record<string, string> = {
    maize: '#22C55E', tomato: '#EF4444', cassava: '#1D6B3A',
    onion: '#F59E0B', rice:   '#3B82F6', plantain: '#8B5CF6',
    yam: '#7C3AED', cowpea: '#EA580C', groundnut: '#0891B2',
  }

  return (
    <div className="p-4 sm:p-6 max-w-screen-xl mx-auto pb-20 md:pb-6">
      <h1 className="text-xl font-bold text-[#0F1111] mb-1">Analytics</h1>
      <p className="text-sm text-[#565959] mb-6">Your earnings, listings, and price performance</p>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Est. income (GHS)',     value: loading ? '...' : `${Math.round(totalIncome).toLocaleString()}`, icon: DollarSign, color: '#22C55E' },
          { label: 'Active listings',       value: loading ? '...' : activeDecls,                                   icon: Package,    color: '#1D6B3A' },
          { label: 'Total stock (kg)',       value: loading ? '...' : totalQty,                                      icon: BarChart2,  color: '#3B82F6' },
          { label: 'Avg forecast (GHS/kg)', value: loading ? '...' : avgPrice,                                      icon: TrendingUp, color: '#7C3AED' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-lg border border-[#DDDDDD] p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-[#565959]">{label}</p>
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}18` }}>
                <Icon className="h-3.5 w-3.5" style={{ color }} />
              </div>
            </div>
            <p className="text-lg font-bold text-[#0F1111]">{value}</p>
          </div>
        ))}
      </div>

      {/* Historical price trend */}
      {(hLoading || history.length > 0) && (
        <div className="bg-white rounded-lg border border-[#DDDDDD] p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm text-[#0F1111]">
              Historical price trend — <span className="capitalize">{histCrop}</span> (GHS/kg, 18 months)
            </h2>
            {hLoading && <Loader2 className="h-4 w-4 animate-spin text-[#565959]" />}
          </div>
          {!hLoading && history.length === 0 ? (
            <p className="text-sm text-[#565959] text-center py-8">No historical price data available</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EEEEEE" />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 11 }} width={40} />
                <Tooltip formatter={(v) => [`GHS ${Number(v).toFixed(2)}/kg`, 'Avg price']} />
                <Line type="monotone" dataKey="avg_price" stroke="#1D6B3A" strokeWidth={2} dot={{ r: 2, fill: '#1D6B3A' }} name="Avg market price" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 mb-6">

        {/* Monthly income — derived from real declarations */}
        <div className="bg-white rounded-lg border border-[#DDDDDD] p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm text-[#0F1111]">Projected income by harvest month (GHS)</h2>
            {loading && <Loader2 className="h-4 w-4 animate-spin text-[#565959]" />}
          </div>
          {!loading && monthly.length === 0 ? (
            <p className="text-sm text-[#565959] text-center py-8">No declaration data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={monthly}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EEEEEE" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={60} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                <Tooltip formatter={(v) => [`GHS ${Number(v).toLocaleString()}`, 'Income']} />
                <Bar dataKey="income" fill="#22C55E" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Market prices per crop — from bulletin */}
        <div className="bg-white rounded-lg border border-[#DDDDDD] p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm text-[#0F1111]">Current market prices (GHS/kg)</h2>
          </div>
          {priceChart.length === 0 ? (
            <p className="text-sm text-[#565959] text-center py-8">No market price data available</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={priceChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EEEEEE" />
                <XAxis dataKey="market" tick={{ fontSize: 9 }} angle={-30} textAnchor="end" height={40} />
                <YAxis tick={{ fontSize: 11 }} width={40} />
                <Tooltip formatter={(v) => [`GHS ${Number(v).toFixed(2)}`, '']} />
                <Legend />
                {farmerCrops.map(crop => (
                  <Line
                    key={crop}
                    type="monotone"
                    dataKey={crop}
                    stroke={CROP_COLORS[crop] ?? '#888'}
                    strokeWidth={2}
                    dot={false}
                    name={crop.replace(/_/g, ' ').replace(/^\w/, x => x.toUpperCase())}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Declarations breakdown */}
      <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
        <div className="px-4 py-3 border-b border-[#EEEEEE] flex items-center justify-between">
          <h2 className="font-semibold text-sm text-[#0F1111]">Your declarations</h2>
          {loading && <Loader2 className="h-4 w-4 animate-spin text-[#565959]" />}
        </div>
        {!loading && decls.length === 0 ? (
          <p className="text-sm text-[#565959] p-6 text-center">No declarations yet. Add one from the dashboard.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F7F7F7] text-xs text-[#565959] uppercase tracking-wide">
                <tr>
                  {['ID', 'Crop', 'Quantity (kg)', 'Harvest date', 'Forecast (GHS/kg)', 'Est. income', 'Status'].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left font-semibold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EEEEEE]">
                {decls.map(d => (
                  <tr key={d.id} className="hover:bg-[#FAFAFA]">
                    <td className="px-4 py-3 text-[#565959] font-mono text-xs">#{d.id}</td>
                    <td className="px-4 py-3 font-medium text-[#0F1111] capitalize">{d.crop}</td>
                    <td className="px-4 py-3 text-[#565959]">{d.quantity_kg.toLocaleString()}</td>
                    <td className="px-4 py-3 text-[#565959] whitespace-nowrap">
                      {new Date(d.harvest_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </td>
                    <td className="px-4 py-3 font-semibold text-[#22C55E]">
                      {d.price_forecast_ghs ? `GHS ${d.price_forecast_ghs.toFixed(2)}` : '—'}
                    </td>
                    <td className="px-4 py-3 font-semibold text-[#0F1111]">
                      {d.price_forecast_ghs
                        ? `GHS ${(d.quantity_kg * d.price_forecast_ghs).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        d.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-[#F0F0F0] text-[#565959]'
                      }`}>
                        {d.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
