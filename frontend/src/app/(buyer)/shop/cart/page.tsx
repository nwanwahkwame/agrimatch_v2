'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { MessageCircle, ShieldCheck, Trash2, ShoppingBag, ArrowRight, RefreshCw } from 'lucide-react'
import API from '@/lib/api'

interface InterestItem {
  declaration_id: number
  crop:           string
  farmer_name:    string
  district:       string
  quantity_bags:  number
  date:           string
}

interface Reservation {
  reservation_id: number
  reference:      string
  provider:       string
  amount_ghs:     number
  crop:           string
  farmer_name:    string
  district:       string
  quantity_bags:  number
  date:           string
}

function fmtCrop(name: string) {
  return name.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function CartPage() {
  const [interests,    setInterests]    = useState<InterestItem[]>([])
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [syncing,      setSyncing]      = useState(false)

  function mergeFromDb(dbItems: Reservation[], local: Reservation[]): Reservation[] {
    const byRef = new Map(local.map(r => [r.reference, r]))
    dbItems.forEach(db => {
      if (!byRef.has(db.reference)) byRef.set(db.reference, db)
    })
    return Array.from(byRef.values())
  }

  async function syncFromDb(current: Reservation[]) {
    const phone = localStorage.getItem('agrimatch_buyer_phone')
    if (!phone) return
    setSyncing(true)
    try {
      const res = await API.get(`/api/reservations/buyer/${encodeURIComponent(phone)}`)
      const dbRows: Reservation[] = (res.data as {
        id: number; reference: string; provider: string; total_ghs: number;
        crop: string; district: string; quantity_bags: number; created_at: string;
      }[]).map(r => ({
        reservation_id: r.id,
        reference:      r.reference,
        provider:       r.provider,
        amount_ghs:     r.total_ghs,
        crop:           r.crop,
        farmer_name:    '',
        district:       r.district,
        quantity_bags:  r.quantity_bags,
        date:           r.created_at,
      }))
      const merged = mergeFromDb(dbRows, current)
      setReservations(merged)
      localStorage.setItem('agrimatch_reservations', JSON.stringify(merged))
    } catch { /* offline or no reservations */ }
    finally { setSyncing(false) }
  }

  useEffect(() => {
    const localInterests    = JSON.parse(localStorage.getItem('agrimatch_interest_items') || '[]') as InterestItem[]
    const localReservations = JSON.parse(localStorage.getItem('agrimatch_reservations')   || '[]') as Reservation[]
    setInterests(localInterests)
    setReservations(localReservations)
    // Mark all as seen — badge resets to 0
    const total = localStorage.getItem('agrimatch_interests') || '0'
    localStorage.setItem('agrimatch_seen', total)
    window.dispatchEvent(new Event('cart-seen'))
    // Try to pull DB reservations for this buyer
    syncFromDb(localReservations)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function removeInterest(idx: number) {
    const updated = interests.filter((_, i) => i !== idx)
    setInterests(updated)
    localStorage.setItem('agrimatch_interest_items', JSON.stringify(updated))
  }

  function removeReservation(idx: number) {
    const updated = reservations.filter((_, i) => i !== idx)
    setReservations(updated)
    localStorage.setItem('agrimatch_reservations', JSON.stringify(updated))
  }

  const totalReserved = reservations.reduce((s, r) => s + r.amount_ghs, 0)
  const totalItems    = interests.length + reservations.length

  if (totalItems === 0) {
    return (
      <div className="mx-auto max-w-screen-xl px-4 py-12 flex flex-col items-center text-center gap-4">
        <ShoppingBag className="h-20 w-20 text-[#DDDDDD]" />
        <h1 className="text-2xl font-bold text-[#0F1111]">Your enquiries are empty</h1>
        <p className="text-sm text-[#565959] max-w-sm">
          Browse the marketplace, express interest in fresh produce listings, or reserve with MoMo — they all appear here.
        </p>
        <Link
          href="/shop"
          className="rounded-full bg-[#22C55E] hover:bg-[#16A34A] text-white font-semibold px-8 py-2.5 text-sm transition-colors flex items-center gap-2"
        >
          Browse Listings <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-screen-xl px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[#0F1111]">My Enquiries</h1>
        {syncing && (
          <span className="flex items-center gap-1.5 text-xs text-[#565959]">
            <RefreshCw className="h-3 w-3 animate-spin" /> Syncing from account...
          </span>
        )}
      </div>

      <div className="grid lg:grid-cols-[1fr_300px] gap-6">

        {/* ── Left column ────────────────────────────────────── */}
        <div className="flex flex-col gap-6">

          {/* Reservations (paid) */}
          {reservations.length > 0 && (
            <div className="bg-white rounded border border-[#DDDDDD]">
              <div className="bg-[#F0FDF4] border-b border-[#DDDDDD] px-4 py-3 flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-[#15803D]" />
                <span className="font-bold text-sm text-[#15803D]">Confirmed Reservations ({reservations.length})</span>
              </div>
              <ul className="divide-y divide-[#EEEEEE]">
                {reservations.map((r, i) => (
                  <li key={r.reference} className="flex items-start gap-4 p-4">
                    <div className="h-14 w-14 rounded bg-[#F0FDF4] flex items-center justify-center shrink-0">
                      <ShieldCheck className="h-6 w-6 text-[#22C55E]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-[#0F1111] text-sm">
                        {fmtCrop(r.crop)} — {r.district}
                      </p>
                      <p className="text-xs text-[#565959]">From: {r.farmer_name}</p>
                      <p className="text-xs text-[#565959]">{r.quantity_bags} bag{r.quantity_bags > 1 ? 's' : ''} · {r.provider}</p>
                      <p className="text-xs font-mono text-[#007185] mt-0.5">Ref: {r.reference}</p>
                      <p className="text-xs text-[#AAAAAA] mt-0.5">{fmtDate(r.date)}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <span className="text-base font-bold text-[#0F1111]">GHS {r.amount_ghs.toFixed(2)}</span>
                      <span className="text-[10px] bg-[#F0FDF4] text-[#15803D] font-semibold px-2 py-0.5 rounded-full border border-[#22C55E]/30">
                        Paid
                      </span>
                      <button onClick={() => removeReservation(i)} className="text-[#AAAAAA] hover:text-red-500 transition-colors">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Express Interests (enquiries) */}
          {interests.length > 0 && (
            <div className="bg-white rounded border border-[#DDDDDD]">
              <div className="bg-[#EFF6FF] border-b border-[#DDDDDD] px-4 py-3 flex items-center gap-2">
                <MessageCircle className="h-4 w-4 text-[#007185]" />
                <span className="font-bold text-sm text-[#007185]">Express Interests ({interests.length})</span>
                <span className="text-xs text-[#565959] ml-1">— farmers will contact you</span>
              </div>
              <ul className="divide-y divide-[#EEEEEE]">
                {interests.map((item, i) => (
                  <li key={`${item.declaration_id}-${i}`} className="flex items-start gap-4 p-4">
                    <div className="h-14 w-14 rounded bg-[#EFF6FF] flex items-center justify-center shrink-0">
                      <MessageCircle className="h-6 w-6 text-[#007185]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-[#0F1111] text-sm">
                        {fmtCrop(item.crop)} — {item.district}
                      </p>
                      <p className="text-xs text-[#565959]">From: {item.farmer_name}</p>
                      <p className="text-xs text-[#565959]">{item.quantity_bags} bag{item.quantity_bags > 1 ? 's' : ''} requested</p>
                      <p className="text-xs text-[#AAAAAA] mt-0.5">{fmtDate(item.date)}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <span className="text-[10px] bg-amber-50 text-amber-700 font-semibold px-2 py-0.5 rounded-full border border-amber-200">
                        Pending contact
                      </span>
                      <Link
                        href={`/shop/${item.declaration_id}`}
                        className="text-xs text-[#007185] hover:underline"
                      >
                        Reserve with MoMo →
                      </Link>
                      <button onClick={() => removeInterest(i)} className="text-[#AAAAAA] hover:text-red-500 transition-colors">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* ── Right: Summary ──────────────────────────────────── */}
        <div className="flex flex-col gap-3 h-fit sticky top-24">
          <div className="bg-white rounded border border-[#DDDDDD] p-4">
            <h2 className="font-bold text-[#0F1111] text-sm mb-3">Summary</h2>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-[#565959]">Reservations ({reservations.length})</span>
              <span className="font-bold text-[#0F1111]">GHS {totalReserved.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm mb-3">
              <span className="text-[#565959]">Interests ({interests.length})</span>
              <span className="text-[#565959]">Awaiting contact</span>
            </div>
            <div className="border-t border-[#DDDDDD] pt-3">
              <div className="flex justify-between font-bold text-[#0F1111]">
                <span>Total paid</span>
                <span className="text-[#15803D]">GHS {totalReserved.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <Link
            href="/shop"
            className="w-full bg-[#22C55E] hover:bg-[#16A34A] text-white font-bold rounded-full py-2.5 text-sm text-center transition-colors flex items-center justify-center gap-2"
          >
            Continue Shopping <ArrowRight className="h-4 w-4" />
          </Link>

          <p className="text-[10px] text-[#AAAAAA] text-center">
            Confirmed reservations are paid. Interests are free enquiries — farmers will reach you within 24 hours.
          </p>
        </div>
      </div>
    </div>
  )
}
