'use client'

import { useState, useEffect } from 'react'
import { Calculator, TrendingUp, Truck, DollarSign, AlertTriangle, CheckCircle, ChevronDown, Loader2, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import API, { getAdminCrops, getAdminDistricts } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

// ─── Types ─────────────────────────────────────────────────────────────────────

interface Crop     { id: number; name: string }
interface District { id: number; district_name: string; region_name: string }

interface ROIResult {
  crop:                  string
  quantity_kg:           number
  source_district:       string
  target_district:       string
  target_market:         string
  forecast_price_per_kg: number
  gross_revenue_ghs:     number
  transport_cost_ghs:    number
  transport_per_kg_ghs:  number
  net_revenue_ghs:       number
  net_per_kg_ghs:        number
  margin_pct:            number
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number) {
  return n.toLocaleString('en-GH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtInt(n: number) {
  return n.toLocaleString('en-GH', { maximumFractionDigits: 0 })
}

// ─── Small stat card ──────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label:   string
  value:   string
  sub?:    string
  accent?: string
}) {
  return (
    <div className="bg-white rounded-lg border border-[#DDDDDD] p-4 flex flex-col gap-1">
      <p className="text-xs text-[#565959]">{label}</p>
      <p className={`text-xl font-bold ${accent ?? 'text-[#0F1111]'}`}>{value}</p>
      {sub && <p className="text-xs text-[#565959]">{sub}</p>}
    </div>
  )
}

// ─── Select wrapper ───────────────────────────────────────────────────────────

function SelectField({
  label,
  value,
  onChange,
  children,
  disabled,
}: {
  label:    string
  value:    string
  onChange: (v: string) => void
  children: React.ReactNode
  disabled?: boolean
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-semibold text-[#0F1111]">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          disabled={disabled}
          className="w-full appearance-none border border-[#DDDDDD] rounded px-3 pr-8 py-2.5 text-sm bg-white outline-none focus:border-[#22C55E] focus:ring-1 focus:ring-[#22C55E] disabled:opacity-50"
        >
          {children}
        </select>
        <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#565959] pointer-events-none" />
      </div>
    </div>
  )
}

// ─── Margin bar ───────────────────────────────────────────────────────────────

function MarginBar({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct))
  const isGood  = pct >= 20
  return (
    <div className="mt-1">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-[#565959]">Net margin</span>
        <span className={`text-sm font-bold ${isGood ? 'text-[#15803D]' : 'text-orange-600'}`}>
          {pct.toFixed(1)}%
        </span>
      </div>
      <div className="h-3 bg-[#F0F2F2] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${isGood ? 'bg-[#22C55E]' : 'bg-orange-400'}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ROICalculatorPage() {
  const { user } = useAuth()

  const [crops,     setCrops]     = useState<Crop[]>([])
  const [districts, setDistricts] = useState<District[]>([])
  const [loading,   setLoading]   = useState(true)

  // Form state
  const [cropId,    setCropId]    = useState('')
  const [bags,      setBags]      = useState('')
  const [srcId,     setSrcId]     = useState('')
  const [tgtId,     setTgtId]     = useState('')

  // Result state
  const [result,    setResult]    = useState<ROIResult | null>(null)
  const [calcLoading, setCalcLoading] = useState(false)
  const [error,     setError]     = useState('')

  // Load reference data
  useEffect(() => {
    Promise.allSettled([
      getAdminCrops(),
      getAdminDistricts(),
    ]).then(([cropsRes, distRes]) => {
      if (cropsRes.status === 'fulfilled') {
        setCrops(cropsRes.value.data as Crop[])
        if ((cropsRes.value.data as Crop[]).length > 0) {
          setCropId(String((cropsRes.value.data as Crop[])[0].id))
        }
      }
      if (distRes.status === 'fulfilled') {
        const list = distRes.value.data as { id: number; district_name: string; region_name: string }[]
        setDistricts(list)
        // Pre-fill source district from session
        const userDistrict = user?.districtId
        if (userDistrict) {
          setSrcId(String(userDistrict))
        } else if (list.length > 0) {
          setSrcId(String(list[0].id))
        }
        if (list.length > 1) setTgtId(String(list[1].id))
      }
    }).finally(() => setLoading(false))
  }, [user?.districtId])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!cropId || !bags || !srcId || !tgtId) {
      setError('Please fill in all fields.')
      return
    }
    if (srcId === tgtId) {
      setError('Source and target district must be different.')
      return
    }
    setError('')
    setCalcLoading(true)
    setResult(null)
    try {
      const selectedCrop = crops.find(c => String(c.id) === cropId)
      const res = await API.get('/api/roi', {
        params: {
          crop:               selectedCrop?.name ?? cropId,
          quantity_kg:        Number(bags) * 100,
          source_district_id: Number(srcId),
          target_district_id: Number(tgtId),
        },
      })
      setResult(res.data as ROIResult)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Could not calculate ROI. Please try again.')
    } finally {
      setCalcLoading(false)
    }
  }

  const selectedCropName = crops.find(c => String(c.id) === cropId)?.name ?? ''
  const quantityKg       = Number(bags) * 100

  return (
    <div className="p-4 sm:p-6 max-w-screen-xl mx-auto pb-20 md:pb-6">

      {/* Header */}
      <div className="mb-6">
        <Link
          href="/seller"
          className="flex items-center gap-1.5 text-sm text-[#007185] hover:underline mb-3"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Dashboard
        </Link>
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-[#22C55E]/10 flex items-center justify-center">
            <Calculator className="h-5 w-5 text-[#22C55E]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#0F1111]">ROI Calculator</h1>
            <p className="text-sm text-[#565959]">Estimate your net return before you sell</p>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-[420px_1fr] gap-6">

        {/* ── Left: Form ───────────────────────────────────────────────── */}
        <div className="bg-white rounded-lg border border-[#DDDDDD] p-5 flex flex-col gap-5 self-start">
          <h2 className="font-bold text-sm text-[#0F1111] border-b border-[#EEEEEE] pb-3">
            Enter Your Details
          </h2>

          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded px-3 py-2.5 text-xs text-red-700">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">

            {/* Crop */}
            <SelectField
              label="Crop *"
              value={cropId}
              onChange={setCropId}
              disabled={loading}
            >
              <option value="">Select a crop...</option>
              {crops.map(c => (
                <option key={c.id} value={String(c.id)}>
                  {c.name.replace(/_/g, ' ').replace(/^\w/, x => x.toUpperCase())}
                </option>
              ))}
            </SelectField>

            {/* Quantity */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-[#0F1111]">
                Quantity (bags) * <span className="font-normal text-[#565959]">1 bag = 100 kg</span>
              </label>
              <input
                type="number"
                min="1"
                value={bags}
                onChange={e => setBags(e.target.value)}
                placeholder="e.g. 50"
                className="border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E] focus:ring-1 focus:ring-[#22C55E]"
              />
              {bags && Number(bags) > 0 && (
                <p className="text-xs text-[#565959]">= {fmtInt(Number(bags) * 100)} kg total</p>
              )}
            </div>

            {/* Source district */}
            <SelectField
              label="Your (Source) District *"
              value={srcId}
              onChange={setSrcId}
              disabled={loading}
            >
              <option value="">Select district...</option>
              {districts.map(d => (
                <option key={d.id} value={String(d.id)}>
                  {d.district_name} ({d.region_name})
                </option>
              ))}
            </SelectField>

            {/* Target district */}
            <SelectField
              label="Target Market District *"
              value={tgtId}
              onChange={setTgtId}
              disabled={loading}
            >
              <option value="">Select district...</option>
              {districts.map(d => (
                <option key={d.id} value={String(d.id)}>
                  {d.district_name} ({d.region_name})
                </option>
              ))}
            </SelectField>

            <button
              type="submit"
              disabled={calcLoading || loading}
              className="w-full bg-[#22C55E] hover:bg-[#16A34A] disabled:opacity-60 text-white font-bold py-3 rounded text-sm transition-colors flex items-center justify-center gap-2 mt-1"
            >
              {calcLoading
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Calculating...</>
                : <><Calculator className="h-4 w-4" /> Calculate ROI</>
              }
            </button>
          </form>
        </div>

        {/* ── Right: Results ────────────────────────────────────────────── */}
        <div className="flex flex-col gap-4">

          {!result && !calcLoading && (
            <div className="bg-white rounded-lg border border-[#DDDDDD] p-10 flex flex-col items-center justify-center text-center gap-3 min-h-[300px]">
              <TrendingUp className="h-12 w-12 text-[#DDDDDD]" />
              <p className="font-semibold text-[#0F1111]">Results will appear here</p>
              <p className="text-sm text-[#565959] max-w-xs">
                Fill in the form on the left and click &ldquo;Calculate ROI&rdquo; to see your estimated returns.
              </p>
            </div>
          )}

          {calcLoading && (
            <div className="bg-white rounded-lg border border-[#DDDDDD] p-10 flex flex-col items-center justify-center gap-3 min-h-[300px]">
              <Loader2 className="h-10 w-10 text-[#22C55E] animate-spin" />
              <p className="text-sm text-[#565959]">Running forecast model...</p>
            </div>
          )}

          {result && !calcLoading && (
            <>
              {/* Margin alert banner */}
              {result.margin_pct < 20 ? (
                <div className="flex items-start gap-3 bg-orange-50 border border-orange-200 rounded-lg px-4 py-3">
                  <AlertTriangle className="h-5 w-5 text-orange-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-orange-800 text-sm">Low margin — consider a closer market</p>
                    <p className="text-xs text-orange-700 mt-0.5">
                      Your estimated margin of {result.margin_pct.toFixed(1)}% is below 20%. Transport costs are eating into your profit.
                      Try selecting a closer target district.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-3 bg-[#F0FDF4] border border-[#22C55E]/40 rounded-lg px-4 py-3">
                  <CheckCircle className="h-5 w-5 text-[#22C55E] shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-[#15803D] text-sm">Good margin</p>
                    <p className="text-xs text-[#15803D]/80 mt-0.5">
                      Your estimated {result.margin_pct.toFixed(1)}% margin looks healthy for this route.
                    </p>
                  </div>
                </div>
              )}

              {/* Summary cards */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <StatCard
                  label="Gross Revenue"
                  value={`GHS ${fmtInt(result.gross_revenue_ghs)}`}
                  sub={`GHS ${fmt(result.forecast_price_per_kg)}/kg forecast`}
                  accent="text-[#0F1111]"
                />
                <StatCard
                  label="Transport Cost"
                  value={`GHS ${fmtInt(result.transport_cost_ghs)}`}
                  sub={`GHS ${fmt(result.transport_per_kg_ghs)}/kg`}
                  accent="text-red-600"
                />
                <StatCard
                  label="Net Revenue"
                  value={`GHS ${fmtInt(result.net_revenue_ghs)}`}
                  sub={`GHS ${fmt(result.net_per_kg_ghs)}/kg`}
                  accent={result.margin_pct >= 20 ? 'text-[#15803D]' : 'text-orange-600'}
                />
              </div>

              {/* Breakdown panel */}
              <div className="bg-white rounded-lg border border-[#DDDDDD] p-5 flex flex-col gap-4">
                <div className="flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-[#22C55E]" />
                  <h3 className="font-bold text-sm text-[#0F1111]">Revenue Breakdown</h3>
                </div>

                {/* Route info */}
                <div className="bg-[#F7F7F7] rounded px-3 py-2.5 text-xs text-[#565959] flex flex-wrap gap-x-4 gap-y-1">
                  <span>
                    <span className="font-semibold text-[#0F1111]">Crop:</span>{' '}
                    {result.crop.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())}
                  </span>
                  <span>
                    <span className="font-semibold text-[#0F1111]">Quantity:</span>{' '}
                    {fmtInt(result.quantity_kg)} kg ({fmtInt(result.quantity_kg / 100)} bags)
                  </span>
                  <span>
                    <span className="font-semibold text-[#0F1111]">From:</span> {result.source_district}
                  </span>
                  <span>
                    <span className="font-semibold text-[#0F1111]">To:</span> {result.target_district}
                  </span>
                  <span>
                    <span className="font-semibold text-[#0F1111]">Market:</span> {result.target_market}
                  </span>
                </div>

                {/* Line items */}
                <div className="flex flex-col divide-y divide-[#EEEEEE]">
                  {[
                    {
                      label:  'Forecast price',
                      sub:    `GHS ${fmt(result.forecast_price_per_kg)}/kg`,
                      value:  '',
                      bold:   false,
                      color:  'text-[#565959]',
                    },
                    {
                      label:  'Gross revenue',
                      sub:    `${fmtInt(result.quantity_kg)} kg × GHS ${fmt(result.forecast_price_per_kg)}`,
                      value:  `GHS ${fmtInt(result.gross_revenue_ghs)}`,
                      bold:   false,
                      color:  'text-[#0F1111]',
                    },
                    {
                      label:  'Transport cost',
                      sub:    `GHS ${fmt(result.transport_per_kg_ghs)}/kg`,
                      value:  `- GHS ${fmtInt(result.transport_cost_ghs)}`,
                      bold:   false,
                      color:  'text-red-600',
                    },
                  ].map(row => (
                    <div key={row.label} className="flex items-center justify-between py-2.5">
                      <div>
                        <p className="text-sm text-[#0F1111]">{row.label}</p>
                        {row.sub && <p className="text-xs text-[#565959]">{row.sub}</p>}
                      </div>
                      {row.value && (
                        <p className={`text-sm font-semibold ${row.color}`}>{row.value}</p>
                      )}
                    </div>
                  ))}

                  {/* Net total */}
                  <div className="flex items-center justify-between py-3 bg-[#F0FDF4] rounded px-3 -mx-3 mt-1">
                    <div>
                      <p className="text-sm font-bold text-[#0F1111]">Net revenue</p>
                      <p className="text-xs text-[#565959]">GHS {fmt(result.net_per_kg_ghs)}/kg</p>
                    </div>
                    <p className={`text-lg font-bold ${result.margin_pct >= 20 ? 'text-[#15803D]' : 'text-orange-600'}`}>
                      GHS {fmtInt(result.net_revenue_ghs)}
                    </p>
                  </div>
                </div>

                {/* Margin bar */}
                <MarginBar pct={result.margin_pct} />

                {/* Transport icon */}
                <div className="flex items-center gap-2 text-xs text-[#565959] pt-1 border-t border-[#EEEEEE]">
                  <Truck className="h-4 w-4 text-[#565959] shrink-0" />
                  Transport estimate uses cooperative logistics rates for this route.
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
