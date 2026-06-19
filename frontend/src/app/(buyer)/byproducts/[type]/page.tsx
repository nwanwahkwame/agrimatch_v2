'use client'

import { use, useState, useEffect } from 'react'
import Link from 'next/link'
import {
  ArrowLeft, Calendar, MapPin, Truck, Package,
  Clock, CheckCircle, Wheat, MessageSquare,
} from 'lucide-react'
import { getByproductListings } from '@/lib/api'

interface ByproductListing {
  byproduct_declaration_id: number
  primary_declaration_id: number
  crop: string
  byproduct_type: string
  estimated_quantity_kg: number
  is_perishable: boolean
  available_date: string
  district: string
  region: string
  distance_km: number
  delivery_cost_ghs: number
  landed_cost_per_kg: number
  perishability_urgency: string
  farmer_name: string
}

const BUYER_DISTRICT_ID = 32

function capitalize(s: string): string {
  return s.replace(/\b\w/g, c => c.toUpperCase())
}

function fmtDate(d: string): string {
  return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

function Skel({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-[#C8D8D2]/40 ${className}`} />
}

const URGENCY_CONFIG: Record<string, { bg: string; text: string; icon: React.ReactNode; label: string }> = {
  stable:    { bg: 'bg-[#E8F5EE]', text: 'text-[#1D6B3A]', icon: <CheckCircle className="h-3.5 w-3.5" />, label: 'Stable'            },
  urgent:    { bg: 'bg-[#FFF8E7]', text: 'text-[#92400E]', icon: <Clock className="h-3.5 w-3.5" />,       label: 'Urgent'            },
  immediate: { bg: 'bg-red-50',    text: 'text-red-700',   icon: <Clock className="h-3.5 w-3.5" />,       label: 'Collect immediately' },
}

function ListingCard({ item, onContact, contacted }: {
  item: ByproductListing
  onContact: (id: number) => void
  contacted: boolean
}) {
  const urg = URGENCY_CONFIG[item.perishability_urgency] ?? URGENCY_CONFIG.stable
  return (
    <div className="rounded-xl border border-[#C8D8D2] bg-white shadow-sm overflow-hidden">
      <div className="p-5">
        <div className="mb-3 flex items-start justify-between gap-2">
          <div>
            <p className="font-semibold text-[#0F1613]">{item.district}</p>
            <p className="text-xs text-[#7A9088]">{item.region} Region · Farmer: {item.farmer_name}</p>
          </div>
          <span className={`flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${urg.bg} ${urg.text}`}>
            {urg.icon}{urg.label}
          </span>
        </div>
        <p className="font-display text-xl font-bold text-[#1D6B3A] mb-3">
          {item.estimated_quantity_kg.toLocaleString()} kg
        </p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-[#445E54] mb-3">
          <span className="flex items-center gap-1.5"><Calendar className="h-3.5 w-3.5 text-[#7A9088]" />{fmtDate(item.available_date)}</span>
          <span className="flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5 text-[#7A9088]" />{item.distance_km == null ? '--' : item.distance_km === 0 ? 'Your district' : `${item.distance_km.toFixed(0)} km`}</span>
          <span className="flex items-center gap-1.5"><Truck className="h-3.5 w-3.5 text-[#7A9088]" />{item.delivery_cost_ghs != null ? `GHS ${item.delivery_cost_ghs.toFixed(0)} delivery` : 'Delivery TBC'}</span>
          <span className="flex items-center gap-1.5"><Wheat className="h-3.5 w-3.5 text-[#7A9088]" />From: {item.crop}</span>
        </div>
        {contacted && (
          <div className="mb-3 flex items-center gap-2 rounded-lg bg-[#E8F5EE] px-3 py-2 text-sm text-[#1D6B3A]">
            <CheckCircle className="h-4 w-4 shrink-0" />Inquiry sent! The farmer will contact you.
          </div>
        )}
      </div>
      <div className="border-t border-[#EEF4F1] p-3">
        <button
          onClick={() => onContact(item.byproduct_declaration_id)}
          disabled={contacted}
          className={`flex w-full items-center justify-center gap-2 rounded-lg border py-2 text-sm font-medium transition-colors ${
            contacted
              ? 'border-[#C8D8D2] text-[#7A9088] cursor-default'
              : 'border-[#1D6B3A] text-[#1D6B3A] hover:bg-[#E8F5EE]'
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          {contacted ? 'Inquiry sent' : 'Contact Farmer'}
        </button>
      </div>
    </div>
  )
}

export default function ByproductTypePage({ params }: { params: Promise<{ type: string }> }) {
  const { type } = use(params)
  const decoded = decodeURIComponent(type)

  const [listings,   setListings]   = useState<ByproductListing[]>([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [contacted,  setContacted]  = useState<Set<number>>(new Set())

  useEffect(() => {
    let alive = true
    setLoading(true); setError('')
    getByproductListings(decoded, { buyer_district_id: BUYER_DISTRICT_ID })
      .then(r => { if (alive) setListings((r.data.results ?? []) as ByproductListing[]) })
      .catch(() => { if (alive) setError(`No listings found for ${capitalize(decoded)}`) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [decoded])

  function handleContact(id: number) {
    setContacted(prev => new Set(prev).add(id))
  }

  const totalKg = listings.reduce((s, l) => s + l.estimated_quantity_kg, 0)

  return (
    <div className="min-h-screen bg-[#F7FAF8]">
      <section className="px-6 py-6" style={{ background: '#145228', backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)', backgroundSize: '20px 20px' }}>
        <div className="mx-auto max-w-screen-xl">
          <Link href="/byproducts" className="mb-3 inline-flex items-center gap-1.5 text-sm text-[#7DCFA0] hover:text-white transition-colors">
            <ArrowLeft className="h-3.5 w-3.5" />All byproducts
          </Link>
          <h1 className="font-display text-2xl font-bold text-white">{capitalize(decoded)} listings</h1>
          {!loading && listings.length > 0 && (
            <p className="mt-1 text-sm text-[#7DCFA0]">{totalKg.toLocaleString()} kg available across {listings.length} listing{listings.length !== 1 ? 's' : ''}</p>
          )}
        </div>
      </section>
      <div className="mx-auto max-w-screen-xl px-6 py-8">
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0,1,2].map(i => (
              <div key={i} className="flex flex-col gap-3 rounded-xl bg-white p-5 shadow-sm border border-[#C8D8D2]">
                <Skel className="h-5 w-40" /><Skel className="h-7 w-24" /><Skel className="h-16 w-full" /><Skel className="h-10 w-full mt-1" />
              </div>
            ))}
          </div>
        ) : error || listings.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl bg-white px-6 py-16 text-center shadow-sm">
            <Package className="mb-4 h-12 w-12 text-[#C8D8D2]" />
            <h2 className="mb-2 font-medium text-[#2D3F38]">No {capitalize(decoded)} listings available</h2>
            <p className="mb-6 text-sm text-[#7A9088]">Check back after the next harvest season</p>
            <Link href="/byproducts" className="rounded-lg border border-[#1D6B3A] px-5 py-2 text-sm font-medium text-[#1D6B3A] hover:bg-[#E8F5EE] transition-colors">
              Back to byproducts
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {listings.map(item => (
              <ListingCard key={item.byproduct_declaration_id} item={item} onContact={handleContact} contacted={contacted.has(item.byproduct_declaration_id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
