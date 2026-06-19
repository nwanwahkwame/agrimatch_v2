'use client'

import { useState, useMemo, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import Image from 'next/image'
import { Star, MessageCircle, Filter, ChevronDown, Search, MapPin, Store } from 'lucide-react'
import API, { getAdminCrops } from '@/lib/api'
import { cropImageSrc } from '@/lib/cropImage'

// ─── Types ─────────────────────────────────────────────────────────────────────

interface Listing {
  declaration_id: number
  farmer_name: string
  district: string
  region: string
  crop: string
  quantity_kg: number
  harvest_date: string
  price_forecast_ghs: number | null
  match_score: number
  csi_flag: string
  distance_km: number
  delivery_cost_ghs: number
  adjusted_harvest_date: string | null
  landed_cost_per_kg: number | null
  is_new?: boolean
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const SORT_OPTIONS = [
  { value: 'match',      label: 'Best Match'          },
  { value: 'price_asc',  label: 'Price: Low to High'  },
  { value: 'price_desc', label: 'Price: High to Low'  },
  { value: 'qty_desc',   label: 'Most Available'      },
]


// ─── Helpers ───────────────────────────────────────────────────────────────────

function scoreToStars(score: number): number {
  if (score >= 0.9) return 5
  if (score >= 0.75) return 4
  if (score >= 0.55) return 3
  if (score >= 0.35) return 2
  return 1
}

function Stars({ score }: { score: number }) {
  const filled = scoreToStars(score)
  return (
    <span className="flex items-center gap-0.5">
      {[1,2,3,4,5].map(i => (
        <Star key={i} className={`h-3 w-3 ${i <= filled ? 'fill-[#22C55E] text-[#22C55E]' : 'fill-gray-200 text-gray-200'}`} />
      ))}
      <span className="text-xs text-[#007185] ml-1">{(score ?? 0).toFixed(2)}</span>
    </span>
  )
}

function Skel() {
  return (
    <div className="bg-white rounded border border-[#DDDDDD] animate-pulse overflow-hidden">
      <div className="bg-gray-200 h-48 w-full" />
      <div className="p-3 flex flex-col gap-2">
        <div className="h-3 bg-gray-200 rounded w-3/4" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
        <div className="h-5 bg-gray-200 rounded w-1/3 mt-1" />
        <div className="h-8 bg-gray-200 rounded mt-2" />
      </div>
    </div>
  )
}

// ─── Product card ──────────────────────────────────────────────────────────────

function ProductCard({ item, cropMeta }: { item: Listing; cropMeta: Record<string, string> }) {
  const label = cropMeta[item.crop] ?? item.crop.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
  const bags  = Math.round(item.quantity_kg / 100)
  const daysUntil = Math.ceil((new Date(item.harvest_date).getTime() - Date.now()) / 86_400_000)
  const inStock = daysUntil <= 21

  return (
    <Link
      href={`/shop/${item.declaration_id}`}
      className="group bg-white rounded border border-[#DDDDDD] hover:shadow-lg transition-shadow overflow-hidden flex flex-col"
    >
      {/* Image */}
      <div className="h-48 relative overflow-hidden">
        <Image
          src={cropImageSrc(item.crop, item.declaration_id)}
          alt={label}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-300"
        />
        {item.csi_flag === 'alert' && (
          <span className="absolute top-2 left-2 bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded">
            Climate Alert
          </span>
        )}
        {item.is_new && (
          <span className="absolute top-2 left-2 bg-[#131921] text-[#22C55E] text-[10px] font-bold px-2 py-0.5 rounded">
            New
          </span>
        )}
        {daysUntil <= 7 && (
          <span className="absolute top-2 right-2 bg-[#CC0C39] text-white text-[10px] font-bold px-2 py-0.5 rounded">
            Urgent
          </span>
        )}
        {inStock && daysUntil > 7 && (
          <span className="absolute top-2 right-2 bg-[#22C55E] text-[#131921] text-[10px] font-bold px-2 py-0.5 rounded">
            Soon
          </span>
        )}
      </div>

      {/* Info */}
      <div className="p-3 flex flex-col flex-1 gap-1">
        {/* Farmer name — the "store" identity */}
        <div className="flex items-center gap-1 mb-0.5">
          <Store className="h-3 w-3 text-[#22C55E] shrink-0" />
          <span className="text-xs font-semibold text-[#15803D] truncate">{item.farmer_name}</span>
        </div>
        <p className="text-sm font-medium text-[#0F1111] leading-snug line-clamp-2 group-hover:text-[#15803D] transition-colors">
          {label} — {item.district}
        </p>
        <p className="text-xs text-[#565959]">{item.region} Region · {bags} bags ({item.quantity_kg.toLocaleString()} kg)</p>

        <Stars score={item.match_score} />

        {item.price_forecast_ghs ? (
          <div className="mt-1">
            <span className="text-lg font-bold text-[#0F1111]">
              GHS {item.price_forecast_ghs.toFixed(2)}
            </span>
            <span className="text-xs text-[#565959]">/kg</span>
          </div>
        ) : (
          <p className="text-sm text-[#565959] mt-1">Price on request</p>
        )}

        <p className="text-xs text-[#007185]">
          {daysUntil <= 0
            ? 'Ready for pickup'
            : daysUntil === 1
              ? 'Harvest tomorrow'
              : `Harvest in ${daysUntil} days`}
        </p>

        <p className="text-xs text-[#565959]">
          {item.distance_km == null
            ? null
            : item.distance_km === 0
              ? 'In your district'
              : `${item.distance_km.toFixed(0)} km away`}
          {item.delivery_cost_ghs > 0 && ` · GHS ${item.delivery_cost_ghs.toFixed(0)} delivery`}
        </p>

        <div className="mt-auto w-full bg-[#22C55E] hover:bg-[#16A34A] text-white text-sm font-semibold rounded py-1.5 flex items-center justify-center gap-2 transition-colors">
          <MessageCircle className="h-4 w-4" />
          Express Interest
        </div>
      </div>
    </Link>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({
  crop, cropLabel, region, allListings, cropMeta, crops, onCropChange, onRegionChange,
}: {
  crop:           string
  cropLabel:      string
  region:         string
  allListings:    Listing[]
  cropMeta:       Record<string, string>
  crops:          string[]
  onCropChange:   (c: string) => void
  onRegionChange: (r: string) => void
}) {
  // Group all listings (no region filter) by region
  const byRegion: Record<string, Listing[]> = {}
  allListings.forEach(l => {
    if (!byRegion[l.region]) byRegion[l.region] = []
    byRegion[l.region].push(l)
  })
  const otherRegions = Object.entries(byRegion)
    .filter(([r]) => r !== region)
    .sort(([, a], [, b]) => b.length - a.length)

  // Case 1: no listings anywhere for this crop
  if (allListings.length === 0) {
    return (
      <div className="bg-white rounded border border-[#DDDDDD] p-10">
        <div className="text-center mb-8">
          <Search className="mx-auto mb-3 h-12 w-12 text-[#DDDDDD]" />
          <p className="font-bold text-[#0F1111] text-lg mb-1">
            No {cropLabel} listings right now
          </p>
          <p className="text-sm text-[#565959]">
            Farmers haven&apos;t declared any {cropLabel} yet. Try a different crop below.
          </p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-[#AAAAAA] mb-3">
            Available crops
          </p>
          <div className="flex flex-wrap gap-2">
            {crops.filter(c => c !== crop).map(c => (
              <button key={c} onClick={() => onCropChange(c)}
                className="px-4 py-2 rounded-full border border-[#DDDDDD] bg-white hover:border-[#22C55E] hover:bg-[#F0FDF4] text-sm font-medium text-[#0F1111] capitalize transition-colors">
                {cropMeta[c] ?? c}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // Case 2: listings exist but not in the filtered region
  return (
    <div className="flex flex-col gap-6">

      {/* Explanation */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg px-5 py-4 flex items-start gap-3">
        <MapPin className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-[#0F1111] text-sm">
            No {cropLabel} listings in {region} right now
          </p>
          <p className="text-xs text-[#565959] mt-0.5">
            Farmers in {region} haven&apos;t declared {cropLabel} yet — but it&apos;s available in {otherRegions.length} other region{otherRegions.length !== 1 ? 's' : ''}.
            You can order from nearby regions below.
          </p>
        </div>
      </div>

      {/* Available in other regions */}
      {otherRegions.map(([r, items]) => (
        <div key={r}>
          {/* Region header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-[#565959]" />
              <span className="font-semibold text-[#0F1111] text-sm">{r} Region</span>
              <span className="text-xs text-[#565959]">— {items.length} listing{items.length !== 1 ? 's' : ''}</span>
            </div>
            <button onClick={() => onRegionChange(r)}
              className="text-xs font-semibold text-[#007185] hover:text-[#15803D] hover:underline">
              See all in {r} →
            </button>
          </div>

          {/* Show top 3 from this region */}
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
            {items.slice(0, 3).map(item => (
              <ProductCard key={item.declaration_id} item={item} cropMeta={cropMeta} />
            ))}
            {/* Overflow card */}
            {items.length > 3 && (
              <button onClick={() => onRegionChange(r)}
                className="rounded border-2 border-dashed border-[#DDDDDD] hover:border-[#22C55E] hover:bg-[#F0FDF4] flex flex-col items-center justify-center gap-2 p-4 transition-colors group min-h-[200px]">
                <span className="text-2xl font-bold text-[#565959] group-hover:text-[#22C55E]">
                  +{items.length - 3}
                </span>
                <span className="text-xs text-[#565959] group-hover:text-[#15803D] text-center">
                  more in {r}
                </span>
              </button>
            )}
          </div>
        </div>
      ))}

      {/* Try another crop */}
      <div className="bg-white rounded border border-[#DDDDDD] p-5">
        <p className="text-sm font-semibold text-[#0F1111] mb-3">
          Or try a different crop in {region}:
        </p>
        <div className="flex flex-wrap gap-2">
          {crops.filter(c => c !== crop).map(c => (
            <button key={c}
              onClick={() => { onCropChange(c) }}
              className="px-4 py-1.5 rounded-full border border-[#DDDDDD] bg-white hover:border-[#22C55E] hover:bg-[#F0FDF4] text-sm font-medium text-[#0F1111] capitalize transition-colors">
              {cropMeta[c] ?? c}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Inner page (needs useSearchParams) ────────────────────────────────────────

function ShopInner() {
  const params = useSearchParams()
  const cropParam   = params.get('crop')   || ''
  const qParam      = params.get('q')      || ''
  const regionParam = params.get('region') || ''
  const viewParam    = params.get('view')   || ''
  const isBestView   = viewParam === 'best'
  const isFreshView  = !cropParam && !qParam && viewParam !== 'best'

  const [activeCrop,   setActiveCrop]   = useState(cropParam || '')
  const cropLabel = (name: string) => name.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
  const [activeRegion, setActiveRegion] = useState(regionParam)
  const [sortBy,       setSortBy]       = useState(isBestView ? 'price_desc' : 'match')
  const isOverviewView = isBestView || isFreshView
  const [maxDist,      setMaxDist]      = useState<number | ''>('')
  const [showFilters,  setShowFilters]  = useState(false)

  // ── Crops (cached 10 min) ────────────────────────────────────────────────────
  const { data: crops = [] } = useQuery<string[]>({
    queryKey: ['crops'],
    queryFn: () =>
      getAdminCrops().then(r =>
        (r.data as { name: string }[]).filter(c => c?.name).map(c => c.name),
      ),
    staleTime: 10 * 60_000,
  })

  const cropMeta = useMemo<Record<string, string>>(() => {
    const meta: Record<string, string> = {}
    crops.forEach(n => { meta[n] = n.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase()) })
    return meta
  }, [crops])

  // ── Listings (cached 2 min, keyed by view/crop/region) ──────────────────────
  const listingsUrl = isBestView && !activeCrop
    ? '/api/listings/best?limit=40'
    : activeCrop
      ? `/api/listings?crop=${encodeURIComponent(activeCrop)}${activeRegion ? `&region=${encodeURIComponent(activeRegion)}` : ''}&limit=100`
      : `/api/listings${activeRegion ? `?region=${encodeURIComponent(activeRegion)}&limit=100` : '?limit=100'}`

  const { data: listings = [], isLoading: loading, isError } = useQuery<Listing[]>({
    queryKey: ['listings', isBestView, activeCrop, activeRegion],
    queryFn: () => API.get(listingsUrl).then(r => r.data.results ?? []),
    staleTime: 2 * 60_000,
  })

  const error = isError ? 'Could not load listings' : ''

  const sorted = [...listings].sort((a, b) => {
    if (sortBy === 'price_asc')  return (a.price_forecast_ghs ?? 999) - (b.price_forecast_ghs ?? 999)
    if (sortBy === 'price_desc') return (b.price_forecast_ghs ?? 0)   - (a.price_forecast_ghs ?? 0)
    if (sortBy === 'qty_desc')   return b.quantity_kg - a.quantity_kg
    return b.match_score - a.match_score
  })

  const filtered = sorted.filter(l => {
    if (activeRegion && l.region !== activeRegion) return false
    if (qParam && !l.district.toLowerCase().includes(qParam.toLowerCase()) &&
        !l.farmer_name?.toLowerCase().includes(qParam.toLowerCase())) return false
    return true
  })

  // Unique regions from current listings for the sidebar filter
  const availableRegions = [...new Set(listings.map(l => l.region).filter(Boolean))].sort()

  return (
    <div className="mx-auto max-w-screen-xl px-4 py-4 flex gap-6">

      {/* ── Sidebar filters ──────────────────────────────────── */}
      <aside className={`w-56 shrink-0 flex-col gap-4 ${showFilters ? 'flex' : 'hidden'} lg:flex`}>
        <div className="bg-white rounded border border-[#DDDDDD] p-4">
          <h3 className="font-bold text-[#0F1111] text-sm border-b border-[#DDDDDD] pb-2 mb-3">Crop</h3>
          <ul className="flex flex-col gap-1.5">
            {crops.map(c => (
              <li key={c}>
                <button
                  onClick={() => setActiveCrop(c)}
                  className={`text-sm w-full text-left px-1 py-0.5 rounded transition-colors ${
                    activeCrop === c
                      ? 'text-[#15803D] font-bold'
                      : 'text-[#007185] hover:text-[#15803D]'
                  }`}
                >
                  {cropMeta[c] ?? c}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-white rounded border border-[#DDDDDD] p-4">
          <h3 className="font-bold text-[#0F1111] text-sm border-b border-[#DDDDDD] pb-2 mb-3">Distance</h3>
          {[50, 100, 200, ''].map(d => (
            <label key={String(d)} className="flex items-center gap-2 text-sm text-[#0F1111] mb-1.5 cursor-pointer">
              <input
                type="radio"
                name="dist"
                checked={maxDist === d}
                onChange={() => setMaxDist(d as number | '')}
                className="accent-[#22C55E]"
              />
              {d === '' ? 'Any distance' : `Up to ${d} km`}
            </label>
          ))}
        </div>

        {/* Region filter */}
        {availableRegions.length > 0 && (
          <div className="bg-white rounded border border-[#DDDDDD] p-4">
            <h3 className="font-bold text-[#0F1111] text-sm border-b border-[#DDDDDD] pb-2 mb-3">Region</h3>
            <label className="flex items-center gap-2 text-sm text-[#0F1111] mb-1.5 cursor-pointer">
              <input type="radio" name="region" checked={activeRegion === ''}
                onChange={() => setActiveRegion('')} className="accent-[#22C55E]" />
              All regions
            </label>
            {availableRegions.map(r => (
              <label key={r} className="flex items-center gap-2 text-sm text-[#0F1111] mb-1.5 cursor-pointer">
                <input type="radio" name="region" checked={activeRegion === r}
                  onChange={() => setActiveRegion(r)} className="accent-[#22C55E]" />
                {r}
              </label>
            ))}
          </div>
        )}
      </aside>

      {/* ── Main content ─────────────────────────────────────── */}
      <div className="flex-1 min-w-0">

        {/* Toolbar */}
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFilters(v => !v)}
              className="lg:hidden flex items-center gap-1.5 border border-[#DDDDDD] rounded px-3 py-1.5 text-sm bg-white"
            >
              <Filter className="h-4 w-4" /> Filters
            </button>
            <p className="text-sm text-[#565959]">
              {loading ? 'Loading...' : `${filtered.length} result${filtered.length !== 1 ? 's' : ''} ${isOverviewView && !activeCrop ? (isBestView ? '— best prices' : activeRegion ? '' : '— all listings') : 'for '}`}
              {!loading && activeCrop && <strong className="text-[#0F1111]">&quot;{cropMeta[activeCrop] ?? activeCrop}&quot;</strong>}
              {!loading && activeRegion && <span className="text-[#565959]"> in {activeRegion}</span>}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-[#565959]">Sort by:</span>
            <div className="relative">
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="appearance-none border border-[#DDDDDD] rounded bg-white px-3 pr-8 py-1.5 text-sm text-[#0F1111] outline-none cursor-pointer"
              >
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-[#565959] pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Region filter banner */}
        {activeRegion && (
          <div className="flex items-center gap-2 mb-3 bg-[#F0FDF4] border border-[#22C55E]/40 rounded-lg px-3 py-2">
            <MapPin className="h-4 w-4 text-[#22C55E] shrink-0" />
            <span className="text-sm text-[#0F1111]">
              Showing listings from <strong>{activeRegion} Region</strong>
            </span>
            <button
              onClick={() => setActiveRegion('')}
              className="ml-auto text-xs text-[#565959] hover:text-red-600 underline"
            >
              Clear filter
            </button>
          </div>
        )}

        {/* Crop tab strip */}
        <div className="flex gap-2 overflow-x-auto mb-4 pb-1">
          {crops.map(c => (
            <button
              key={c}
              onClick={() => setActiveCrop(c)}
              className={`flex items-center gap-1.5 shrink-0 px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                activeCrop === c
                  ? 'bg-[#232F3E] text-white border-[#232F3E]'
                  : 'bg-white text-[#0F1111] border-[#DDDDDD] hover:border-[#999]'
              }`}
            >
              {cropMeta[c] ?? c}
            </button>
          ))}
        </div>

        {/* Grid */}
        {loading ? (
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
            {[...Array(8)].map((_, i) => <Skel key={i} />)}
          </div>
        ) : error ? (
          <div className="bg-white rounded border border-[#DDDDDD] p-10 text-center">
            <p className="font-semibold text-red-600 mb-1">Could not load listings</p>
            <p className="text-sm text-[#565959]">Please try refreshing the page.</p>
          </div>
        ) : filtered.length > 0 ? (
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
            {filtered.map(item => (
              <ProductCard key={item.declaration_id} item={item} cropMeta={cropMeta} />
            ))}
          </div>
        ) : (
          <EmptyState
            crop={activeCrop}
            cropLabel={cropMeta[activeCrop] ?? activeCrop}
            region={activeRegion}
            allListings={sorted}
            cropMeta={cropMeta}
            crops={crops}
            onCropChange={setActiveCrop}
            onRegionChange={setActiveRegion}
          />
        )}
      </div>
    </div>
  )
}

// ─── Page wrapper ──────────────────────────────────────────────────────────────

export default function ShopPage() {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-screen-xl px-4 py-8 grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
        {[...Array(8)].map((_, i) => <Skel key={i} />)}
      </div>
    }>
      <ShopInner />
    </Suspense>
  )
}
