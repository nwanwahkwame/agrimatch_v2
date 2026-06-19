'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Clock, CheckCircle, Package, Leaf, AlertTriangle } from 'lucide-react'
import { getByproducts } from '@/lib/api'

// ─── Types ─────────────────────────────────────────────────────────────────────

interface ByproductSummary {
  byproduct_type: string
  total_listings: number
  total_kg_available: number
  is_perishable: boolean
  nearest_available_date: string
  regions_available: string[]
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function capitalize(s: string): string {
  return s.replace(/\b\w/g, c => c.toUpperCase())
}

function fmtDate(d: string): string {
  return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function daysUntil(dateStr: string): number {
  const diff = new Date(dateStr).getTime() - Date.now()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

function Skel({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-[#C8D8D2]/40 ${className}`} />
}

// ─── Byproduct Card ────────────────────────────────────────────────────────────

function ByproductCard({ item }: { item: ByproductSummary }) {
  const days = daysUntil(item.nearest_available_date)
  const isUrgent = item.is_perishable && days <= 7

  return (
    <div className="flex flex-col overflow-hidden rounded-xl bg-white shadow-sm border border-[#C8D8D2]">
      <div className="flex-1 p-5">
        {/* Type + perishable badge */}
        <div className="mb-4 flex items-start justify-between gap-2">
          <h3 className="font-display text-base font-bold text-[#0F1613]">
            {capitalize(item.byproduct_type)}
          </h3>
          {item.is_perishable ? (
            <span className="flex shrink-0 items-center gap-1 rounded-full bg-[#FFF8E7] px-2.5 py-1 text-xs font-medium text-[#92400E]">
              <Clock className="h-3 w-3" /> Perishable
            </span>
          ) : (
            <span className="flex shrink-0 items-center gap-1 rounded-full bg-[#E8F5EE] px-2.5 py-1 text-xs font-medium text-[#1D6B3A]">
              <CheckCircle className="h-3 w-3" /> Stable
            </span>
          )}
        </div>

        {/* Quantity + listings */}
        <div className="mb-3">
          <p className="font-display text-2xl font-bold text-[#1D6B3A]">
            {item.total_kg_available.toLocaleString()} kg
          </p>
          <p className="text-sm text-[#7A9088]">
            {item.total_listings} listing{item.total_listings !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Region tags */}
        <div className="mb-4 flex flex-wrap gap-1.5">
          {item.regions_available.map(r => (
            <span key={r} className="rounded-full bg-[#EEF4F1] px-2.5 py-0.5 text-xs text-[#445E54]">
              {r}
            </span>
          ))}
        </div>

        {/* Availability */}
        <div className="mb-1 text-xs text-[#7A9088]">
          Available from:{' '}
          <strong className="text-[#2D3F38]">{fmtDate(item.nearest_available_date)}</strong>
        </div>

        {/* Urgency bar */}
        {isUrgent && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-[#FFF8E7] px-3 py-2">
            <Clock className="h-4 w-4 text-[#B45309]" />
            <span className="text-xs font-medium text-[#92400E]">
              Urgent — expires in {days} day{days !== 1 ? 's' : ''}
            </span>
          </div>
        )}
      </div>

      <div className="border-t border-[#EEF4F1] p-3">
        <Link
          href={`/byproducts/${encodeURIComponent(item.byproduct_type)}`}
          className="block w-full rounded-lg bg-[#1D6B3A] py-2 text-center text-sm font-semibold text-white transition-colors hover:bg-[#145228]"
        >
          View Listings
        </Link>
      </div>
    </div>
  )
}

// ─── Section block ─────────────────────────────────────────────────────────────

function Section({
  title,
  subtitle,
  headerBg,
  icon,
  items,
  loading,
}: {
  title: string
  subtitle: string
  headerBg: string
  icon: React.ReactNode
  items: ByproductSummary[]
  loading: boolean
}) {
  if (!loading && items.length === 0) return null

  return (
    <section>
      <div className={`mb-4 rounded-xl px-5 py-4 ${headerBg}`}>
        <h2 className="font-display text-lg font-bold text-white flex items-center gap-2">
          {icon}{title}
        </h2>
        <p className="mt-0.5 text-sm text-white/80">{subtitle}</p>
      </div>
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {[0, 1].map(i => (
            <div key={i} className="flex flex-col gap-3 rounded-xl bg-white p-5 shadow-sm border border-[#C8D8D2]">
              <Skel className="h-5 w-36" />
              <Skel className="h-8 w-28" />
              <Skel className="h-3 w-full" />
              <Skel className="h-10 w-full mt-2" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {items.map(item => (
            <ByproductCard key={item.byproduct_type} item={item} />
          ))}
        </div>
      )}
    </section>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function ByproductsPage() {
  const [items, setItems] = useState<ByproductSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    getByproducts()
      .then(r => {
        if (!alive) return
        setItems(r.data as ByproductSummary[])
      })
      .catch(() => { if (alive) setError('Byproduct data unavailable') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const perishable = items.filter(i => i.is_perishable)
  const stable     = items.filter(i => !i.is_perishable)

  const totalKg      = items.reduce((s, i) => s + i.total_kg_available, 0)
  const perishCount  = perishable.length

  return (
    <div className="min-h-screen bg-[#F7FAF8]">

      {/* Header */}
      <section
        className="px-6 py-10"
        style={{
          background: '#145228',
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
        }}
      >
        <div className="mx-auto max-w-screen-xl">
          <div className="flex items-center gap-2 mb-3">
            <Leaf className="h-5 w-5 text-[#4DB876]" />
            <span className="text-sm text-[#7DCFA0] font-medium">Circular Economy</span>
          </div>
          <h1 className="font-display text-3xl font-bold text-white">Waste to Wealth</h1>
          <p className="mt-2 max-w-xl text-sm text-[#7DCFA0]">
            Agricultural byproducts available from Ghana&apos;s smallholder farms.
            Turn husks, stalks, and skins into additional income streams.
          </p>

          {/* Stat strip */}
          {!loading && items.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-6">
              {[
                { label: 'Byproduct types',       value: items.length.toString()                 },
                { label: 'Total kg available',     value: `${totalKg.toLocaleString()} kg`        },
                { label: 'Perishable items',       value: perishCount.toString(), warn: perishCount > 0 },
              ].map(({ label, value, warn }) => (
                <div key={label}>
                  <p className={`font-display text-2xl font-bold ${warn ? 'text-[#F59E0B]' : 'text-white'}`}>
                    {value}
                  </p>
                  <p className="text-xs text-[#7DCFA0]">{label}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Content */}
      <div className="mx-auto max-w-screen-xl space-y-10 px-6 py-8">
        {error ? (
          <div className="rounded-xl bg-white p-10 text-center shadow-sm">
            <Package className="mx-auto mb-3 h-10 w-10 text-[#C8D8D2]" />
            <p className="text-sm text-[#7A9088]">{error}</p>
          </div>
        ) : (
          <>
            <Section
              title="Urgent — Perishable Items"
              icon={<AlertTriangle className="h-5 w-5" />}
              subtitle="These items need collection soon to avoid spoilage"
              headerBg="bg-[#B45309]"
              items={perishable}
              loading={loading}
            />
            <Section
              title="Stable Byproducts"
              icon={<CheckCircle className="h-5 w-5" />}
              subtitle="Non-perishable agricultural materials available for collection"
              headerBg="bg-[#1D6B3A]"
              items={stable}
              loading={loading}
            />
          </>
        )}
      </div>
    </div>
  )
}
