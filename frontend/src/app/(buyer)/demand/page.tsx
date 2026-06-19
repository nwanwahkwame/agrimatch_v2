'use client'

import { useState, useEffect, useCallback } from 'react'
import Image from 'next/image'
import { ChevronDown, Phone, Clock, ChevronUp, PlusCircle, Filter, AlertCircle, Loader2, Package } from 'lucide-react'
import API, { getAdminCrops, getAdminRegions } from '@/lib/api'
import { cropImageSrc } from '@/lib/cropImage'

// ─── Types ─────────────────────────────────────────────────────────────────────

interface Crop   { id: number; name: string }
interface Region { id: number; name: string }

interface DemandRequest {
  id:           number
  crop:         string
  quantity_kg:  number
  region:       string
  target_date:  string | null
  buyer_name:   string
  buyer_phone:  string
  notes:        string | null
  created_at:   string
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function capitalize(s: string) {
  return s.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60_000)
  const hours = Math.floor(diff / 3_600_000)
  const days  = Math.floor(diff / 86_400_000)
  if (mins < 60)   return `${mins}m ago`
  if (hours < 24)  return `${hours}h ago`
  return `${days}d ago`
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

// ─── Skeleton card ────────────────────────────────────────────────────────────

function RequestSkel() {
  return (
    <div className="bg-white rounded-lg border border-[#DDDDDD] animate-pulse overflow-hidden flex flex-col">
      <div className="h-36 bg-gray-200 w-full" />
      <div className="p-4 flex flex-col gap-2">
        <div className="h-4 bg-gray-200 rounded w-3/4" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
        <div className="h-3 bg-gray-200 rounded w-2/3" />
        <div className="h-9 bg-gray-200 rounded mt-2" />
      </div>
    </div>
  )
}

// ─── Demand request card ──────────────────────────────────────────────────────

function RequestCard({ req }: { req: DemandRequest }) {
  const bags = Math.round(req.quantity_kg / 100)
  return (
    <div className="bg-white rounded-lg border border-[#DDDDDD] hover:shadow-md transition-shadow overflow-hidden flex flex-col">

      {/* Crop image */}
      <div className="relative h-36 w-full shrink-0">
        <Image
          src={cropImageSrc(req.crop, req.id)}
          alt={capitalize(req.crop)}
          fill
          className="object-cover"
        />
        {/* Time badge */}
        <span className="absolute top-2 right-2 flex items-center gap-1 bg-black/50 backdrop-blur-sm rounded-full px-2.5 py-1 text-[10px] text-white">
          <Clock className="h-3 w-3" /> {timeAgo(req.created_at)}
        </span>
      </div>

      {/* Body */}
      <div className="p-4 flex flex-col gap-2 flex-1">

        {/* Crop + region */}
        <div>
          <p className="font-bold text-[#0F1111] text-base leading-snug">
            {capitalize(req.crop)}
          </p>
          <p className="text-xs text-[#565959]">{req.region} Region</p>
        </div>

        {/* Quantity */}
        <p className="text-sm text-[#565959]">
          <span className="font-semibold text-[#0F1111]">{bags} bags</span>
          {' '}({req.quantity_kg.toLocaleString()} kg)
        </p>

        {/* Needed by */}
        {req.target_date && (
          <p className="text-xs text-[#565959]">
            Needed by:{' '}
            <span className="font-semibold text-[#0F1111]">{fmtDate(req.target_date)}</span>
          </p>
        )}

        {/* Buyer */}
        <p className="text-xs text-[#565959]">
          Buyer: <span className="font-medium text-[#0F1111]">{req.buyer_name}</span>
        </p>

        {/* Notes */}
        {req.notes && (
          <p className="text-xs text-[#565959] italic line-clamp-2">{req.notes}</p>
        )}

        {/* Contact button */}
        <a
          href={`tel:${req.buyer_phone}`}
          className="mt-auto pt-2 w-full flex items-center justify-center gap-2 bg-[#131921] hover:bg-[#232F3E] text-[#22C55E] font-bold text-sm py-2.5 rounded transition-colors"
        >
          <Phone className="h-4 w-4" />
          Contact Buyer
        </a>
      </div>
    </div>
  )
}

// ─── Post form ────────────────────────────────────────────────────────────────

interface PostFormProps {
  crops:   Crop[]
  regions: Region[]
  onPosted: () => void
}

function PostForm({ crops, regions, onPosted }: PostFormProps) {
  const [form, setForm] = useState({
    crop:        '',
    quantity_kg: '',
    region:      '',
    target_date: '',
    buyer_name:  '',
    buyer_phone: '',
    notes:       '',
  })
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [success, setSuccess] = useState(false)

  function set(key: string, value: string) {
    setForm(f => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.crop || !form.quantity_kg || !form.region || !form.buyer_name || !form.buyer_phone) {
      setError('Please fill in all required fields.')
      return
    }
    setError('')
    setLoading(true)
    try {
      await API.post('/api/demand', {
        crop:        form.crop,
        quantity_kg: Number(form.quantity_kg) * 100,
        region:      form.region,
        target_date: form.target_date || undefined,
        buyer_name:  form.buyer_name.trim(),
        buyer_phone: form.buyer_phone.trim(),
        notes:       form.notes.trim() || undefined,
      })
      setSuccess(true)
      setForm({ crop: '', quantity_kg: '', region: '', target_date: '', buyer_name: '', buyer_phone: '', notes: '' })
      setTimeout(() => {
        setSuccess(false)
        onPosted()
      }, 1800)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Could not post request. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="bg-[#F0FDF4] border border-[#22C55E]/40 rounded-lg p-6 flex flex-col items-center gap-2 text-center">
        <div className="h-10 w-10 rounded-full bg-[#22C55E]/10 flex items-center justify-center">
          <PlusCircle className="h-5 w-5 text-[#22C55E]" />
        </div>
        <p className="font-bold text-[#15803D] text-sm">Request posted!</p>
        <p className="text-xs text-[#565959]">Farmers will be able to see and respond to your request.</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">

      {error && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded px-3 py-2.5 text-xs text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" /> {error}
        </div>
      )}

      {/* Crop */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-semibold text-[#0F1111]">Crop *</label>
        <div className="relative">
          <select
            value={form.crop}
            onChange={e => set('crop', e.target.value)}
            className="w-full appearance-none border border-[#DDDDDD] rounded px-3 pr-8 py-2.5 text-sm bg-white outline-none focus:border-[#22C55E]"
          >
            <option value="">Select a crop...</option>
            {crops.map(c => (
              <option key={c.id} value={c.name}>{capitalize(c.name)}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#565959] pointer-events-none" />
        </div>
      </div>

      {/* Quantity */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-semibold text-[#0F1111]">
          Quantity (bags) * <span className="font-normal text-[#565959]">1 bag = 100 kg</span>
        </label>
        <input
          type="number"
          min="1"
          value={form.quantity_kg}
          onChange={e => set('quantity_kg', e.target.value)}
          placeholder="e.g. 20"
          className="border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E]"
        />
      </div>

      {/* Region */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-semibold text-[#0F1111]">Region *</label>
        <div className="relative">
          <select
            value={form.region}
            onChange={e => set('region', e.target.value)}
            className="w-full appearance-none border border-[#DDDDDD] rounded px-3 pr-8 py-2.5 text-sm bg-white outline-none focus:border-[#22C55E]"
          >
            <option value="">Select region...</option>
            {regions.map(r => (
              <option key={r.id} value={r.name}>{r.name}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#565959] pointer-events-none" />
        </div>
      </div>

      {/* Target date */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-semibold text-[#0F1111]">
          Needed by <span className="font-normal text-[#565959]">(optional)</span>
        </label>
        <input
          type="date"
          value={form.target_date}
          onChange={e => set('target_date', e.target.value)}
          min={new Date().toISOString().slice(0, 10)}
          className="border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E]"
        />
      </div>

      {/* Buyer name */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-semibold text-[#0F1111]">Your Name *</label>
        <input
          type="text"
          value={form.buyer_name}
          onChange={e => set('buyer_name', e.target.value)}
          placeholder="Full name"
          className="border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E]"
        />
      </div>

      {/* Phone */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-semibold text-[#0F1111]">Phone Number *</label>
        <div className="flex items-center border border-[#DDDDDD] rounded overflow-hidden focus-within:border-[#22C55E]">
          <span className="bg-[#F0F2F2] px-3 py-2.5 text-sm text-[#565959] border-r border-[#DDDDDD]">+233</span>
          <input
            type="tel"
            value={form.buyer_phone}
            onChange={e => set('buyer_phone', e.target.value)}
            placeholder="24 000 0000"
            className="flex-1 px-3 py-2.5 text-sm outline-none"
          />
        </div>
      </div>

      {/* Notes */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-semibold text-[#0F1111]">
          Notes <span className="font-normal text-[#565959]">(optional)</span>
        </label>
        <textarea
          value={form.notes}
          onChange={e => set('notes', e.target.value)}
          placeholder="Any specific requirements, quality grade, etc."
          rows={3}
          className="border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E] resize-none"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-[#22C55E] hover:bg-[#16A34A] disabled:opacity-60 text-white font-bold py-3 rounded text-sm transition-colors flex items-center justify-center gap-2"
      >
        {loading
          ? <><Loader2 className="h-4 w-4 animate-spin" /> Posting...</>
          : <><PlusCircle className="h-4 w-4" /> Post Request</>
        }
      </button>
    </form>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DemandBoardPage() {
  const [crops,     setCrops]     = useState<Crop[]>([])
  const [regions,   setRegions]   = useState<Region[]>([])
  const [requests,  setRequests]  = useState<DemandRequest[]>([])
  const [refLoading, setRefLoading] = useState(true)
  const [listLoading, setListLoading] = useState(true)

  // Filters
  const [filterCrop,   setFilterCrop]   = useState('')
  const [filterRegion, setFilterRegion] = useState('')

  // Form panel toggle
  const [showForm, setShowForm] = useState(false)

  // Load crops + regions
  useEffect(() => {
    Promise.allSettled([
      getAdminCrops(),
      getAdminRegions(),
    ]).then(([cropsRes, regionsRes]) => {
      if (cropsRes.status === 'fulfilled')   setCrops(cropsRes.value.data as Crop[])
      if (regionsRes.status === 'fulfilled') {
        const raw = regionsRes.value.data
        // API may return [{id, name}] or [{id, region_name}]
        const list = (raw as Record<string, unknown>[]).map((r, i) => ({
          id:   (r.id as number) ?? i,
          name: (r.name ?? r.region_name ?? r.region ?? String(r)) as string,
        }))
        setRegions(list)
      }
    }).finally(() => setRefLoading(false))
  }, [])

  // Load demand requests
  const fetchRequests = useCallback(() => {
    setListLoading(true)
    const params: Record<string, string> = {}
    if (filterCrop)   params.crop   = filterCrop
    if (filterRegion) params.region = filterRegion
    API.get('/api/demand', { params })
      .then(r => setRequests(r.data as DemandRequest[]))
      .catch(() => setRequests([]))
      .finally(() => setListLoading(false))
  }, [filterCrop, filterRegion])

  useEffect(() => { fetchRequests() }, [fetchRequests])

  function handlePosted() {
    setShowForm(false)
    fetchRequests()
  }

  return (
    <div className="mx-auto max-w-screen-xl px-4 py-6 pb-20 md:pb-6">

      {/* Page header */}
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#0F1111]">Buyer Demand Board</h1>
          <p className="text-sm text-[#565959]">See what buyers are looking for, or post your own request</p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="flex items-center gap-2 bg-[#22C55E] hover:bg-[#16A34A] text-white font-bold text-sm px-4 py-2 rounded transition-colors"
        >
          {showForm ? <ChevronUp className="h-4 w-4" /> : <PlusCircle className="h-4 w-4" />}
          Post a Request
        </button>
      </div>

      <div className={`grid gap-6 items-start ${showForm ? 'lg:grid-cols-[380px_1fr]' : ''}`}>

        {/* ── Left: post form (collapsible on mobile, always visible on lg if open) */}
        {showForm && (
          <div className="bg-white rounded-lg border border-[#DDDDDD] p-5 flex flex-col gap-4 self-start">
            <div className="flex items-center justify-between border-b border-[#EEEEEE] pb-3">
              <h2 className="font-bold text-sm text-[#0F1111]">Post a Request</h2>
              <button
                onClick={() => setShowForm(false)}
                className="text-xs text-[#565959] hover:text-[#0F1111] underline"
              >
                Cancel
              </button>
            </div>
            <PostForm
              crops={crops}
              regions={regions}
              onPosted={handlePosted}
            />
          </div>
        )}

        {/* ── Right: filter + cards grid */}
        <div className="flex flex-col gap-4 min-w-0">

          {/* Filter bar */}
          <div className="bg-white rounded-lg border border-[#DDDDDD] px-4 py-3 flex flex-wrap items-center gap-3">
            <Filter className="h-4 w-4 text-[#565959] shrink-0" />
            <span className="text-xs font-semibold text-[#0F1111]">Filter:</span>

            {/* Crop filter */}
            <div className="relative">
              <select
                value={filterCrop}
                onChange={e => setFilterCrop(e.target.value)}
                className="appearance-none border border-[#DDDDDD] rounded px-3 pr-7 py-1.5 text-sm bg-white outline-none focus:border-[#22C55E]"
                disabled={refLoading}
              >
                <option value="">All crops</option>
                {crops.map(c => (
                  <option key={c.id} value={c.name}>{capitalize(c.name)}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#565959] pointer-events-none" />
            </div>

            {/* Region filter */}
            <div className="relative">
              <select
                value={filterRegion}
                onChange={e => setFilterRegion(e.target.value)}
                className="appearance-none border border-[#DDDDDD] rounded px-3 pr-7 py-1.5 text-sm bg-white outline-none focus:border-[#22C55E]"
                disabled={refLoading}
              >
                <option value="">All regions</option>
                {regions.map(r => (
                  <option key={r.id} value={r.name}>{r.name}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#565959] pointer-events-none" />
            </div>

            {(filterCrop || filterRegion) && (
              <button
                onClick={() => { setFilterCrop(''); setFilterRegion('') }}
                className="text-xs text-[#565959] hover:text-red-600 underline"
              >
                Clear
              </button>
            )}

            <span className="ml-auto text-xs text-[#565959]">
              {listLoading ? 'Loading...' : `${requests.length} request${requests.length !== 1 ? 's' : ''}`}
            </span>
          </div>

          {/* Cards */}
          {listLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
              {[...Array(6)].map((_, i) => <RequestSkel key={i} />)}
            </div>
          ) : requests.length === 0 ? (
            <div className="bg-white rounded-lg border border-[#DDDDDD] p-12 flex flex-col items-center gap-3 text-center">
              <Package className="h-12 w-12 text-gray-200" />
              <p className="font-semibold text-[#0F1111]">No open requests</p>
              <p className="text-sm text-[#565959]">
                {filterCrop || filterRegion
                  ? 'Try clearing the filters to see all requests.'
                  : 'Be the first to post a request using the button above.'}
              </p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {requests.map(r => <RequestCard key={r.id} req={r} />)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
