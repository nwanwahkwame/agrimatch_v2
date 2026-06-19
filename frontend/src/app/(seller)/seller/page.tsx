'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { TrendingUp, TrendingDown, Package, PlusCircle, AlertTriangle, CheckCircle, Minus, Lightbulb, Leaf, Truck, Clock } from 'lucide-react'
import API from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { farmerDbId } from '@/lib/auth'
import { cropImageSrc } from '@/lib/cropImage'

interface Declaration {
  id: number
  crop: string
  quantity_kg: number
  harvest_date: string
  status: string
  price_forecast_ghs: number | null
  csi_flag: string
  byproduct_count: number
}

interface StrategyNumbers {
  current_price_ghs: number | null
  price_change_pct: number | null
  net_after_delivery_ghs: number | null
  total_expected_income_ghs: number | null
}

interface Recommendation {
  crop: string
  composite_score: number
  recommendation_strength: string
  reason: string
}

interface Byproduct {
  byproduct_declaration_id: number
  byproduct_type: string
  crop: string
  estimated_quantity_kg: number
  is_perishable: boolean
  available_date: string
  district: string
  perishability_urgency: string
}

interface TransportJob {
  job_id: number
  departure_date: string | null
  destination_market: string | null
  group_size: number
  shared_cost_ghs: number
  saving_ghs: number
  status: string
  provider_name: string | null
  provider_phone: string | null
  co_farmers: { name: string; district: string }[]
}

interface StrategyCard {
  declaration_id: number
  crop: string
  urgency: string
  headline: string
  body: string
  action: string
  numbers: StrategyNumbers
  csi_flag: string
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function CropThumb({ crop, seed }: { crop: string; seed?: number }) {
  return (
    <Image
      src={cropImageSrc(crop || 'maize', seed)}
      alt={crop || 'crop'}
      width={28}
      height={28}
      className="rounded object-cover shrink-0"
    />
  )
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function CsiChip({ flag }: { flag: string }) {
  const cfg = {
    normal: { bg: 'bg-green-100', text: 'text-green-700',  label: 'Normal'   },
    watch:  { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Watch'    },
    alert:  { bg: 'bg-red-100',   text: 'text-red-700',    label: 'Alert'    },
  }[flag] ?? { bg: 'bg-gray-100', text: 'text-gray-600', label: flag }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cfg.bg} ${cfg.text}`}>
      {cfg.label}
    </span>
  )
}

function ActionChip({ action }: { action: string }) {
  const cfg = {
    sell_now:  { bg: 'bg-red-500',    text: 'text-white',       label: 'Sell Now'  },
    sell_soon: { bg: 'bg-[#22C55E]',  text: 'text-[#131921]',   label: 'Sell Soon' },
    neutral:   { bg: 'bg-gray-200',   text: 'text-gray-700',    label: 'Hold'      },
  }[action] ?? { bg: 'bg-gray-200', text: 'text-gray-600', label: action }
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-bold ${cfg.bg} ${cfg.text}`}>
      {cfg.label}
    </span>
  )
}

function Skel({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-gray-200 ${className}`} />
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function SellerDashboard() {
  const { user }                  = useAuth()
  const farmerId                  = farmerDbId(user)
  const [decls,       setDecls]       = useState<Declaration[]>([])
  const [strategies,  setStrategies]  = useState<StrategyCard[]>([])
  const [recs,        setRecs]        = useState<Recommendation[]>([])
  const [byproducts,  setByproducts]  = useState<Byproduct[]>([])
  const [logisticsJobs, setLogisticsJobs] = useState<TransportJob[]>([])
  const [loading,     setLoading]     = useState(true)

  useEffect(() => {
    let alive = true
    Promise.allSettled([
      API.get(`/api/declarations/farmer/${farmerId}`),
      API.get(`/api/strategy/farmer/${farmerId}`),
      API.get(`/api/recommend/farmer/${farmerId}`),
      API.get(`/api/byproducts/farmer/${farmerId}`),
      API.get(`/api/logistics/farmer/${farmerId}`),
    ]).then(([dRes, sRes, rRes, bRes, lRes]) => {
      if (!alive) return
      if (dRes.status === 'fulfilled') setDecls(dRes.value.data as Declaration[])
      if (sRes.status === 'fulfilled') setStrategies((sRes.value.data.strategies ?? []) as StrategyCard[])
      if (rRes.status === 'fulfilled') setRecs((rRes.value.data.recommendations ?? []) as Recommendation[])
      if (bRes.status === 'fulfilled') setByproducts((bRes.value.data.byproducts ?? []) as Byproduct[])
      if (lRes.status === 'fulfilled') setLogisticsJobs((lRes.value.data.transport_jobs ?? []) as TransportJob[])
    }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [farmerId])

  const totalKg     = decls.reduce((s, d) => s + d.quantity_kg, 0)
  const estRevenue  = decls.reduce((s, d) => s + (d.price_forecast_ghs ?? 0) * d.quantity_kg, 0)
  const alerts      = decls.filter(d => d.csi_flag === 'alert').length
  const sellNowCount = strategies.filter(s => s.urgency === 'sell_now').length

  return (
    <div className="p-6 flex flex-col gap-6">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#0F1111]">Seller Dashboard</h1>
          <p className="text-sm text-[#565959]">Welcome back, {user?.name ?? 'Farmer'}</p>
        </div>
        <Link
          href="/seller/new"
          className="flex items-center gap-2 bg-[#22C55E] hover:bg-[#4ADE80] text-[#131921] font-bold text-sm px-4 py-2 rounded transition-colors"
        >
          <PlusCircle className="h-4 w-4" /> Add a Listing
        </Link>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {loading ? (
          [...Array(4)].map((_, i) => <Skel key={i} className="h-24 rounded-lg" />)
        ) : ([
          { label: 'Active listings',  value: decls.length.toString(),          sub: 'declarations',     icon: <Package className="h-5 w-5 text-[#22C55E]" />,      accent: false },
          { label: 'Total stock',      value: `${(totalKg/1000).toFixed(1)}t`,  sub: `${totalKg.toLocaleString()} kg`, icon: <Package className="h-5 w-5 text-[#007185]" />, accent: false },
          { label: 'Est. revenue',     value: `GHS ${(estRevenue/1000).toFixed(1)}k`, sub: 'at forecast price', icon: <TrendingUp className="h-5 w-5 text-green-600" />, accent: true },
          { label: 'Sell now alerts',  value: sellNowCount.toString(),           sub: `${alerts} climate alert${alerts !== 1 ? 's' : ''}`, icon: <AlertTriangle className="h-5 w-5 text-red-500" />, accent: sellNowCount > 0 },
        ].map(({ label, value, sub, icon, accent }) => (
          <div
            key={label}
            className={`rounded-lg border p-4 flex flex-col gap-2 ${
              accent ? 'bg-[#F0FDF4] border-[#22C55E]/40' : 'bg-white border-[#DDDDDD]'
            }`}
          >
            <div className="flex items-center justify-between">{icon}<span /></div>
            <p className="text-xl font-bold text-[#0F1111]">{value}</p>
            <p className="text-xs text-[#565959]">{label}</p>
            <p className="text-xs text-[#999]">{sub}</p>
          </div>
        )))}
      </div>

      {/* Sell strategies */}
      {strategies.length > 0 && (
        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#EEEEEE] flex items-center justify-between">
            <h2 className="font-bold text-[#0F1111] text-sm">AI Sell Strategies</h2>
            <span className="text-xs text-[#565959]">Powered by XGBoost + LSTM forecasts</span>
          </div>
          <div className="divide-y divide-[#EEEEEE]">
            {strategies.slice(0, 5).map(s => {
              const pct = s.numbers?.price_change_pct ?? null
              const up  = pct !== null && pct > 0
              return (
                <div key={`${s.declaration_id}-${s.crop}`} className="px-5 py-3 flex items-center gap-4 flex-wrap">
                  <CropThumb crop={s.crop} seed={s.declaration_id} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[#0F1111] capitalize">{s.crop}</p>
                    <p className="text-xs text-[#565959] truncate">{s.body}</p>
                  </div>
                  <ActionChip action={s.urgency} />
                  {pct !== null && (
                    <span className={`flex items-center gap-0.5 text-sm font-semibold ${up ? 'text-green-600' : 'text-red-500'}`}>
                      {up ? <TrendingUp className="h-4 w-4" /> : pct === 0 ? <Minus className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                      {Math.abs(pct).toFixed(1)}%
                    </span>
                  )}
                  {s.numbers?.total_expected_income_ghs && (
                    <span className="text-sm font-bold text-[#0F1111]">GHS {s.numbers.total_expected_income_ghs.toFixed(0)}</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Harvest delay alerts */}
      {!loading && decls.some(d => d.csi_flag === 'warning' || d.csi_flag === 'alert') && (
        <div className="flex flex-col gap-2">
          {decls.filter(d => d.csi_flag === 'warning' || d.csi_flag === 'alert').map(d => (
            <div key={d.id} className={`flex items-start gap-3 rounded-lg border px-5 py-3 ${d.csi_flag === 'alert' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
              <Clock className={`h-4 w-4 shrink-0 mt-0.5 ${d.csi_flag === 'alert' ? 'text-red-500' : 'text-amber-500'}`} />
              <div>
                <p className={`font-semibold text-sm ${d.csi_flag === 'alert' ? 'text-red-700' : 'text-amber-700'}`}>
                  Harvest delay risk — {d.crop.replace(/_/g,' ').replace(/^\w/,c=>c.toUpperCase())}
                </p>
                <p className="text-xs text-[#565959] mt-0.5">
                  Climate {d.csi_flag === 'alert' ? 'alert' : 'warning'} detected in your district. Your harvest date may be delayed. Consider contacting buyers to update your expected delivery timeline.
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AI crop recommendations */}
      {!loading && recs.length > 0 && (
        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#EEEEEE] flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-[#F59E0B]" />
            <h2 className="font-bold text-[#0F1111] text-sm">AI Crop Recommendations</h2>
            <span className="text-xs text-[#565959] ml-auto">Based on your district climate, supply, and forecast prices</span>
          </div>
          <div className="divide-y divide-[#EEEEEE]">
            {recs.map(r => (
              <div key={r.crop} className="px-5 py-3 flex items-center gap-4 flex-wrap">
                <CropThumb crop={r.crop} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[#0F1111] capitalize">{r.crop.replace(/_/g,' ')}</p>
                  <p className="text-xs text-[#565959] truncate">{r.reason}</p>
                </div>
                <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                  r.recommendation_strength === 'strong' ? 'bg-green-100 text-green-700' :
                  r.recommendation_strength === 'moderate' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-gray-100 text-gray-600'
                }`}>
                  {r.recommendation_strength}
                </span>
                <span className="text-xs text-[#565959]">{(r.composite_score * 100).toFixed(0)}% score</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cooperative logistics jobs */}
      {!loading && logisticsJobs.length > 0 && (
        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#EEEEEE] flex items-center gap-2">
            <Truck className="h-4 w-4 text-blue-600" />
            <h2 className="font-bold text-[#0F1111] text-sm">Cooperative Transport</h2>
            <span className="text-xs text-[#565959] ml-auto">{logisticsJobs.length} job{logisticsJobs.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="divide-y divide-[#EEEEEE]">
            {logisticsJobs.map(job => (
              <div key={job.job_id} className="px-5 py-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-6">
                <div className="flex-1 flex flex-col gap-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      job.status === 'assigned'  ? 'bg-green-100 text-green-700' :
                      job.status === 'completed' ? 'bg-blue-100 text-blue-700' :
                      'bg-yellow-100 text-yellow-700'
                    }`}>
                      {job.status === 'assigned' ? 'Provider assigned' : job.status === 'completed' ? 'Completed' : 'Awaiting provider'}
                    </span>
                    <span className="text-xs text-[#565959]">Job #{job.job_id}</span>
                  </div>
                  <p className="text-sm font-semibold text-[#0F1111]">
                    {job.destination_market ? `Destination: ${job.destination_market}` : 'Destination TBC'}
                  </p>
                  <p className="text-xs text-[#565959]">
                    {job.departure_date ? `Pickup: ${new Date(job.departure_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}` : 'Pickup date TBC'}
                    {' · '}{job.group_size} farmer{job.group_size !== 1 ? 's' : ''} sharing
                  </p>
                  {job.co_farmers.length > 0 && (
                    <p className="text-xs text-[#565959]">
                      Co-farmers: {job.co_farmers.map(f => `${f.name} (${f.district})`).join(', ')}
                    </p>
                  )}
                </div>
                <div className="flex flex-col gap-1 shrink-0 text-right">
                  {job.provider_name ? (
                    <div className="bg-[#F0FDF4] rounded-lg px-3 py-2 text-sm">
                      <p className="font-semibold text-[#15803D]">{job.provider_name}</p>
                      <p className="text-xs text-[#565959]">{job.provider_phone}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-amber-600 font-medium">Provider being assigned...</p>
                  )}
                  <p className="text-xs text-[#565959]">
                    Your share: <strong className="text-[#0F1111]">GHS {job.shared_cost_ghs.toFixed(2)}</strong>
                  </p>
                  {job.saving_ghs > 0 && (
                    <p className="text-xs text-green-600 font-medium">Saving GHS {job.saving_ghs.toFixed(2)}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Byproduct listings */}
      {!loading && byproducts.length > 0 && (
        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#EEEEEE] flex items-center gap-2">
            <Leaf className="h-4 w-4 text-[#22C55E]" />
            <h2 className="font-bold text-[#0F1111] text-sm">My Byproduct Listings</h2>
            <span className="text-xs text-[#565959] ml-auto">{byproducts.length} item{byproducts.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#F7F7F7] border-b border-[#EEEEEE]">
                  {['Type', 'From crop', 'Quantity (kg)', 'Available', 'District', 'Urgency'].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-[#565959]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {byproducts.map((b, i) => (
                  <tr key={b.byproduct_declaration_id} className={`border-b border-[#EEEEEE] hover:bg-[#F7F7F7] ${i % 2 ? 'bg-[#FAFAFA]' : ''}`}>
                    <td className="px-4 py-2.5 font-medium text-[#0F1111] capitalize">{b.byproduct_type.replace(/_/g,' ')}</td>
                    <td className="px-4 py-2.5 text-[#565959] capitalize">{b.crop}</td>
                    <td className="px-4 py-2.5 text-[#565959]">{b.estimated_quantity_kg.toLocaleString()}</td>
                    <td className="px-4 py-2.5 text-[#565959]">{new Date(b.available_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</td>
                    <td className="px-4 py-2.5 text-[#565959]">{b.district}</td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        b.perishability_urgency === 'urgent' ? 'bg-red-100 text-red-700' :
                        b.perishability_urgency === 'soon'   ? 'bg-yellow-100 text-yellow-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {b.perishability_urgency}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Listings table */}
      <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#EEEEEE] flex items-center justify-between">
          <h2 className="font-bold text-[#0F1111] text-sm">My Listings</h2>
          <Link href="/seller/listings" className="text-xs text-[#007185] hover:underline">
            Manage inventory
          </Link>
        </div>

        {loading ? (
          <div className="p-4 flex flex-col gap-3">
            {[...Array(3)].map((_, i) => <Skel key={i} className="h-10" />)}
          </div>
        ) : decls.length === 0 ? (
          <div className="p-10 text-center">
            <Package className="mx-auto h-10 w-10 text-gray-300 mb-3" />
            <p className="text-sm text-[#565959] mb-3">No active listings yet</p>
            <Link href="/seller/new" className="text-sm text-[#007185] hover:underline font-semibold">
              + Add your first listing
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#F7F7F7] border-b border-[#EEEEEE]">
                {['Crop', 'Quantity', 'Harvest date', 'Forecast price', 'Climate', 'Byproducts'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-[#565959]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {decls.map((d, i) => (
                <tr key={d.id} className={`border-b border-[#EEEEEE] hover:bg-[#F7F7F7] transition-colors ${i % 2 ? 'bg-[#FAFAFA]' : ''}`}>
                  <td className="px-4 py-2.5 font-medium text-[#0F1111]">
                    <span className="flex items-center gap-2"><CropThumb crop={d.crop} seed={d.id} />{d.crop}</span>
                  </td>
                  <td className="px-4 py-2.5 text-[#565959]">{d.quantity_kg.toLocaleString()} kg</td>
                  <td className="px-4 py-2.5 text-[#565959]">{fmtDate(d.harvest_date)}</td>
                  <td className="px-4 py-2.5 font-semibold text-[#0F1111]">
                    {d.price_forecast_ghs ? `GHS ${d.price_forecast_ghs.toFixed(2)}/kg` : '—'}
                  </td>
                  <td className="px-4 py-2.5"><CsiChip flag={d.csi_flag} /></td>
                  <td className="px-4 py-2.5 text-[#565959]">
                    {d.byproduct_count > 0
                      ? <span className="flex items-center gap-1 text-[#007185]"><CheckCircle className="h-3.5 w-3.5" /> {d.byproduct_count}</span>
                      : '—'}
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
