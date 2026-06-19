'use client'

import { useState, useEffect, useMemo } from 'react'
import { CalendarDays, ChevronDown, Loader2, Leaf, AlertTriangle, CloudSun } from 'lucide-react'
import API, { getAdminDistricts } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { farmerDbId } from '@/lib/auth'

// ─── Types ─────────────────────────────────────────────────────────────────────

type AdviceCode = 'plant_now' | 'plant_soon' | 'prepare' | 'wait'
type ClimateRisk = 'low' | 'moderate' | 'high'

interface CropAdvisory {
  crop: string
  label: string
  growing_days: number
  optimal_plant_date: string
  days_to_plant: number
  next_peak_month: string
  next_peak_date: string
  advice: AdviceCode
  window_label: string
  climate_risk: ClimateRisk
  climate_note: string
  csi_score: number
}

interface AdvisoryResponse {
  district_id: number
  generated_date: string
  crops: CropAdvisory[]
}

interface District {
  id: number
  name: string
  region: string
}

// ─── Advice config ─────────────────────────────────────────────────────────────

const ADVICE_CONFIG: Record<AdviceCode, { label: string; cls: string; dotCls: string; order: number }> = {
  plant_now:  { label: 'Plant Now',  cls: 'bg-[#22C55E] text-white',             dotCls: 'bg-[#22C55E]', order: 0 },
  plant_soon: { label: 'Plant Soon', cls: 'bg-yellow-400 text-[#131921]',         dotCls: 'bg-yellow-400', order: 1 },
  prepare:    { label: 'Prepare',    cls: 'bg-blue-500 text-white',               dotCls: 'bg-blue-500', order: 2 },
  wait:       { label: 'Wait',       cls: 'bg-gray-300 text-[#565959]',           dotCls: 'bg-gray-400', order: 3 },
}

const RISK_CONFIG: Record<ClimateRisk, { label: string; cls: string; icon: typeof AlertTriangle }> = {
  low:      { label: 'Low risk',      cls: 'text-green-600',  icon: CloudSun },
  moderate: { label: 'Moderate risk', cls: 'text-yellow-600', icon: AlertTriangle },
  high:     { label: 'High risk',     cls: 'text-red-600',    icon: AlertTriangle },
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function daysBetween(a: string, b: string) {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86_400_000)
}

// ─── Timeline bar ─────────────────────────────────────────────────────────────

function Timeline({ crop }: { crop: CropAdvisory }) {
  const today        = new Date()
  const plantDate    = new Date(crop.optimal_plant_date)
  const harvestDate  = new Date(plantDate.getTime() + crop.growing_days * 86_400_000)
  const peakDate     = new Date(crop.next_peak_date)

  // Compute positions as % within [today, peakDate] window
  const totalSpan    = Math.max(peakDate.getTime() - today.getTime(), 1)
  const plantPct     = Math.min(100, Math.max(0, ((plantDate.getTime()   - today.getTime()) / totalSpan) * 100))
  const harvestPct   = Math.min(100, Math.max(0, ((harvestDate.getTime() - today.getTime()) / totalSpan) * 100))

  return (
    <div className="mt-3">
      <p className="text-xs text-[#565959] font-semibold mb-1.5 uppercase tracking-wide">Timeline</p>
      <div className="relative h-5">
        {/* Track */}
        <div className="absolute inset-y-0 left-0 right-0 flex items-center">
          <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
            {/* Growth window */}
            <div
              className="absolute h-2 bg-[#22C55E]/30 rounded-full"
              style={{ left: `${plantPct}%`, right: `${100 - harvestPct}%` }}
            />
          </div>
        </div>

        {/* Today dot */}
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-[#131921] border-2 border-white shadow" title="Today" />

        {/* Plant dot */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-[#22C55E] border-2 border-white shadow"
          style={{ left: `${plantPct}%` }}
          title={`Plant: ${fmtDate(crop.optimal_plant_date)}`}
        />

        {/* Harvest dot */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-[#1D6B3A] border-2 border-white shadow"
          style={{ left: `${harvestPct}%` }}
          title={`Harvest: ${fmtDate(harvestDate.toISOString().slice(0,10))}`}
        />

        {/* Peak star */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-yellow-400 border-2 border-white shadow"
          style={{ left: '100%' }}
          title={`Peak: ${crop.next_peak_month}`}
        />
      </div>

      {/* Labels */}
      <div className="flex justify-between mt-1 text-[10px] text-[#565959]">
        <span>Today</span>
        <span className="text-[#22C55E] font-medium">Plant {fmtDate(crop.optimal_plant_date)}</span>
        <span className="text-[#1D6B3A] font-medium">Harvest</span>
        <span className="text-yellow-600 font-medium">Peak {crop.next_peak_month}</span>
      </div>
    </div>
  )
}

// ─── Crop card ─────────────────────────────────────────────────────────────────

function CropCard({ crop }: { crop: CropAdvisory }) {
  const advice = ADVICE_CONFIG[crop.advice]
  const risk   = RISK_CONFIG[crop.climate_risk]
  const RiskIcon = risk.icon

  return (
    <div className={`bg-white rounded-lg border overflow-hidden transition-shadow hover:shadow-md ${
      crop.advice === 'plant_now' ? 'border-[#22C55E]/60' : 'border-[#DDDDDD]'
    }`}>
      {/* Card header */}
      <div className="flex items-start justify-between gap-3 px-4 pt-4 pb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-[#0F1111] text-base capitalize leading-tight">
              {crop.label || crop.crop.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())}
            </h3>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold shrink-0 ${advice.cls}`}>
              {advice.label}
            </span>
          </div>
          <p className="text-xs text-[#565959] mt-0.5">
            {crop.growing_days}-day growing cycle &middot; {crop.window_label}
          </p>
        </div>
        {/* CSI score badge */}
        <div className="shrink-0 text-center">
          <div className={`text-lg font-black leading-none ${
            crop.csi_score >= 70 ? 'text-[#22C55E]' :
            crop.csi_score >= 45 ? 'text-yellow-500' :
                                   'text-red-500'
          }`}>
            {crop.csi_score}
          </div>
          <div className="text-[9px] text-[#999] uppercase tracking-wide">CSI</div>
        </div>
      </div>

      {/* Detail grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 px-4 pb-3 text-sm">
        <div>
          <p className="text-xs text-[#565959]">Optimal planting date</p>
          <p className="font-semibold text-[#0F1111]">
            {fmtDate(crop.optimal_plant_date)}
            {crop.days_to_plant === 0 && (
              <span className="ml-1.5 text-[10px] font-bold text-[#22C55E]">TODAY</span>
            )}
            {crop.days_to_plant > 0 && (
              <span className="ml-1.5 text-[10px] text-[#565959]">in {crop.days_to_plant}d</span>
            )}
          </p>
        </div>
        <div>
          <p className="text-xs text-[#565959]">Next price peak</p>
          <p className="font-semibold text-yellow-600">{crop.next_peak_month}</p>
        </div>
        <div className="col-span-2">
          <p className="text-xs text-[#565959]">Climate risk</p>
          <div className="flex items-center gap-1.5 mt-0.5">
            <RiskIcon className={`h-3.5 w-3.5 shrink-0 ${risk.cls}`} />
            <span className={`text-sm font-semibold ${risk.cls}`}>{risk.label}</span>
            <span className="text-xs text-[#565959]">&mdash; {crop.climate_note}</span>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="px-4 pb-4">
        <Timeline crop={crop} />
      </div>
    </div>
  )
}

// ─── Skeleton ──────────────────────────────────────────────────────────────────

function CardSkel() {
  return (
    <div className="bg-white rounded-lg border border-[#DDDDDD] p-4 animate-pulse">
      <div className="flex items-start gap-3 mb-3">
        <div className="flex-1">
          <div className="h-5 bg-gray-200 rounded w-40 mb-2" />
          <div className="h-3 bg-gray-200 rounded w-28" />
        </div>
        <div className="h-8 w-8 bg-gray-200 rounded" />
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="h-10 bg-gray-200 rounded" />
        <div className="h-10 bg-gray-200 rounded" />
        <div className="h-8 bg-gray-200 rounded col-span-2" />
      </div>
      <div className="h-8 bg-gray-100 rounded" />
    </div>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

const ADVICE_ORDER: AdviceCode[] = ['plant_now', 'plant_soon', 'prepare', 'wait']

export default function PlantingCalendarPage() {
  const { user, loading: authLoading } = useAuth()
  const farmerId = farmerDbId(user)

  // District from session, or user picks one
  const sessionDistrict = user?.districtId ?? null
  const [districtId,  setDistrictId]  = useState<number | null>(sessionDistrict)
  const [districts,   setDistricts]   = useState<District[]>([])
  const [distLoading, setDistLoading] = useState(false)

  const [advisory,  setAdvisory]  = useState<AdvisoryResponse | null>(null)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')

  // Load districts if we need the fallback selector
  useEffect(() => {
    if (sessionDistrict) return   // have district from session — no need
    setDistLoading(true)
    getAdminDistricts()
      .then(r => {
        const raw = r.data as { id: number; district_name: string; region_name: string }[]
        setDistricts(raw.map(d => ({ id: d.id, name: d.district_name, region: d.region_name })))
      })
      .catch(() => {})
      .finally(() => setDistLoading(false))
  }, [sessionDistrict])

  // Keep districtId in sync when auth resolves
  useEffect(() => {
    if (user?.districtId && !districtId) setDistrictId(user.districtId)
  }, [user?.districtId])

  // Fetch advisory whenever districtId changes
  useEffect(() => {
    if (!districtId) return
    let alive = true
    setLoading(true)
    setError('')
    setAdvisory(null)
    API.get(`/api/planting/advisory?district_id=${districtId}`)
      .then(r => { if (alive) setAdvisory(r.data) })
      .catch(() => { if (alive) setError('Could not load planting advisory. Please try again.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [districtId])

  // Sort crops by advice priority
  const sortedCrops = useMemo(() => {
    if (!advisory) return []
    return [...advisory.crops].sort(
      (a, b) => ADVICE_ORDER.indexOf(a.advice) - ADVICE_ORDER.indexOf(b.advice)
    )
  }, [advisory])

  // Counts by advice
  const counts = useMemo(() => {
    const c: Record<AdviceCode, number> = { plant_now: 0, plant_soon: 0, prepare: 0, wait: 0 }
    sortedCrops.forEach(cr => { c[cr.advice]++ })
    return c
  }, [sortedCrops])

  const selectedDistrict = districts.find(d => d.id === districtId)

  return (
    <div className="p-4 sm:p-6 max-w-screen-xl mx-auto pb-20 md:pb-6">

      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Leaf className="h-5 w-5 text-[#22C55E]" />
            <h1 className="text-xl font-bold text-[#0F1111]">Planting Calendar</h1>
          </div>
          <p className="text-sm text-[#565959]">
            AI-powered planting windows based on climate and price forecasts
          </p>
        </div>

        {/* District selector — shown when session has no district */}
        {!sessionDistrict && (
          <div className="flex flex-col gap-1 shrink-0">
            <label className="text-xs font-semibold text-[#565959]">Your district</label>
            <div className="relative">
              {distLoading ? (
                <div className="flex items-center gap-2 border border-[#DDDDDD] rounded px-3 py-2 text-sm text-[#565959] bg-white">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading districts...
                </div>
              ) : (
                <>
                  <select
                    value={districtId ?? ''}
                    onChange={e => setDistrictId(e.target.value ? parseInt(e.target.value) : null)}
                    className="appearance-none border border-[#DDDDDD] rounded bg-white pl-3 pr-8 py-2 text-sm text-[#0F1111] outline-none focus:border-[#22C55E] cursor-pointer min-w-[200px]"
                  >
                    <option value="">Select district...</option>
                    {districts.map(d => (
                      <option key={d.id} value={d.id}>{d.name} ({d.region})</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#565959] pointer-events-none" />
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* District label when from session */}
      {sessionDistrict && selectedDistrict && (
        <div className="flex items-center gap-2 mb-5 text-sm text-[#565959]">
          <CalendarDays className="h-4 w-4 text-[#22C55E]" />
          Advisory for <strong className="text-[#0F1111]">{selectedDistrict.name} District, {selectedDistrict.region}</strong>
          {advisory && (
            <span className="text-xs text-[#999]">
              &middot; Generated {fmtDate(advisory.generated_date)}
            </span>
          )}
        </div>
      )}

      {/* No district selected prompt */}
      {!districtId && !authLoading && (
        <div className="bg-[#F0FDF4] border border-[#22C55E]/40 rounded-lg px-5 py-8 text-center">
          <CalendarDays className="mx-auto h-10 w-10 text-[#22C55E] mb-3 opacity-60" />
          <p className="font-semibold text-[#0F1111] mb-1">Select your district to view planting windows</p>
          <p className="text-sm text-[#565959]">
            Your personalised planting calendar will appear here.
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 mb-5">
          {error}
        </div>
      )}

      {/* Summary chips */}
      {!loading && advisory && sortedCrops.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-5">
          {(Object.entries(counts) as [AdviceCode, number][])
            .filter(([, n]) => n > 0)
            .map(([code, n]) => {
              const cfg = ADVICE_CONFIG[code]
              return (
                <div key={code} className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${cfg.cls}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${cfg.dotCls} opacity-70`} />
                  {n} crop{n !== 1 ? 's' : ''}: {cfg.label}
                </div>
              )
            })}
        </div>
      )}

      {/* Cards */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => <CardSkel key={i} />)}
        </div>
      ) : advisory && sortedCrops.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sortedCrops.map(crop => (
            <CropCard key={crop.crop} crop={crop} />
          ))}
        </div>
      ) : advisory && sortedCrops.length === 0 ? (
        <div className="bg-white rounded-lg border border-[#DDDDDD] p-10 text-center">
          <Leaf className="mx-auto h-8 w-8 text-gray-300 mb-3" />
          <p className="text-[#565959] text-sm">No crop advisories available for this district yet.</p>
        </div>
      ) : null}
    </div>
  )
}
