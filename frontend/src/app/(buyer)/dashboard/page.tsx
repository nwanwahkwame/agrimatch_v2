'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { Heart, Trash2, TrendingUp, Bell, BellOff, ShoppingBag, ArrowRight, Star } from 'lucide-react'
import { cropImageSrc } from '@/lib/cropImage'

interface WatchedListing {
  declaration_id: number
  crop: string
  farmer_name: string
  district: string
  price_forecast_ghs: number | null
  added_at: string
}

interface PriceAlert {
  crop: string
  threshold_ghs: number
  phone: string
  active: boolean
  created_at: string
}

function fmtCrop(name: string) {
  return name.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const hours = Math.floor(diff / 3_600_000)
  if (hours < 1) return 'Just now'
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function BuyerDashboardPage() {
  const [watchlist, setWatchlist] = useState<WatchedListing[]>([])
  const [alerts,    setAlerts]    = useState<PriceAlert[]>([])
  const [showAlertForm, setShowAlertForm] = useState(false)
  const [alertForm, setAlertForm] = useState({ crop: '', threshold: '', phone: '' })

  useEffect(() => {
    const w = JSON.parse(localStorage.getItem('agrimatch_watchlist') || '[]') as WatchedListing[]
    const a = JSON.parse(localStorage.getItem('agrimatch_price_alerts') || '[]') as PriceAlert[]
    setWatchlist(w)
    setAlerts(a)
  }, [])

  function removeFromWatchlist(id: number) {
    const updated = watchlist.filter(w => w.declaration_id !== id)
    setWatchlist(updated)
    localStorage.setItem('agrimatch_watchlist', JSON.stringify(updated))
  }

  function addAlert(e: React.FormEvent) {
    e.preventDefault()
    if (!alertForm.crop || !alertForm.threshold || !alertForm.phone) return
    const newAlert: PriceAlert = {
      crop:          alertForm.crop.toLowerCase(),
      threshold_ghs: parseFloat(alertForm.threshold),
      phone:         alertForm.phone,
      active:        true,
      created_at:    new Date().toISOString(),
    }
    const updated = [...alerts, newAlert]
    setAlerts(updated)
    localStorage.setItem('agrimatch_price_alerts', JSON.stringify(updated))
    setAlertForm({ crop: '', threshold: '', phone: '' })
    setShowAlertForm(false)
  }

  function toggleAlert(i: number) {
    const updated = alerts.map((a, idx) => idx === i ? { ...a, active: !a.active } : a)
    setAlerts(updated)
    localStorage.setItem('agrimatch_price_alerts', JSON.stringify(updated))
  }

  function removeAlert(i: number) {
    const updated = alerts.filter((_, idx) => idx !== i)
    setAlerts(updated)
    localStorage.setItem('agrimatch_price_alerts', JSON.stringify(updated))
  }

  const CROPS = ['Maize','Tomato','Onion','Cassava','Rice','Plantain','Yam','Cowpea','Groundnut','Pepper','Garden Egg']

  return (
    <div className="mx-auto max-w-screen-xl px-4 py-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#0F1111]">My Dashboard</h1>
          <p className="text-sm text-[#565959] mt-0.5">Your saved listings and price alerts</p>
        </div>
        <Link href="/shop" className="flex items-center gap-2 bg-[#22C55E] hover:bg-[#16A34A] text-white font-bold text-sm px-4 py-2 rounded transition-colors">
          <ShoppingBag className="h-4 w-4" /> Browse Marketplace
        </Link>
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-6">

        {/* ── Watchlist ─────────────────────────────────────── */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-[#0F1111] flex items-center gap-2">
              <Heart className="h-4 w-4 text-red-500" /> Saved Listings
              {watchlist.length > 0 && (
                <span className="text-xs bg-[#F0F0F0] text-[#565959] px-2 py-0.5 rounded-full">{watchlist.length}</span>
              )}
            </h2>
          </div>

          {watchlist.length === 0 ? (
            <div className="bg-white rounded border border-[#DDDDDD] p-10 text-center">
              <Heart className="mx-auto h-12 w-12 text-gray-200 mb-3" />
              <p className="font-semibold text-[#0F1111] mb-1">No saved listings yet</p>
              <p className="text-xs text-[#565959] mb-4">Browse listings and click the heart icon to save them here.</p>
              <Link href="/shop" className="inline-flex items-center gap-2 text-sm text-[#007185] hover:underline font-semibold">
                Browse Marketplace <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          ) : (
            <div className="grid gap-4 grid-cols-2 sm:grid-cols-3">
              {watchlist.map(w => (
                <div key={w.declaration_id} className="bg-white rounded border border-[#DDDDDD] overflow-hidden flex flex-col group">
                  <div className="h-36 relative overflow-hidden">
                    <Image src={cropImageSrc(w.crop, w.declaration_id)} alt={fmtCrop(w.crop)} fill className="object-cover" />
                    <button onClick={() => removeFromWatchlist(w.declaration_id)}
                      className="absolute top-2 right-2 h-7 w-7 rounded-full bg-white/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-50">
                      <Trash2 className="h-3.5 w-3.5 text-red-500" />
                    </button>
                  </div>
                  <div className="p-2.5 flex flex-col flex-1 gap-1">
                    <p className="text-sm font-semibold text-[#0F1111]">{fmtCrop(w.crop)}</p>
                    <p className="text-xs text-[#565959] truncate">{w.farmer_name || w.district}</p>
                    {w.price_forecast_ghs && (
                      <p className="text-sm font-bold text-[#0F1111]">GHS {w.price_forecast_ghs.toFixed(2)}<span className="text-[10px] font-normal text-[#565959]">/kg</span></p>
                    )}
                    <p className="text-[10px] text-[#AAAAAA]">{timeAgo(w.added_at)}</p>
                    <Link href={`/shop/${w.declaration_id}`}
                      className="mt-auto block text-center text-xs font-semibold text-[#007185] hover:text-[#15803D] transition-colors py-1">
                      View listing →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Price alerts sidebar ──────────────────────────── */}
        <div className="flex flex-col gap-4">
          <div className="bg-white rounded border border-[#DDDDDD] overflow-hidden">
            <div className="px-4 py-3 border-b border-[#EEEEEE] flex items-center justify-between">
              <h2 className="font-bold text-sm text-[#0F1111] flex items-center gap-2">
                <Bell className="h-4 w-4 text-[#22C55E]" /> Price Alerts
              </h2>
              <button onClick={() => setShowAlertForm(v => !v)}
                className="text-xs font-semibold text-[#007185] hover:text-[#15803D]">
                {showAlertForm ? 'Cancel' : '+ Add alert'}
              </button>
            </div>

            {showAlertForm && (
              <form onSubmit={addAlert} className="p-4 border-b border-[#EEEEEE] flex flex-col gap-3 bg-[#F0FDF4]">
                <p className="text-xs text-[#565959]">Get notified when a crop price drops below your target.</p>
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-[#0F1111]">Crop</label>
                  <select value={alertForm.crop} onChange={e => setAlertForm(f => ({...f, crop: e.target.value}))}
                    className="border border-[#888] rounded px-2 py-1.5 text-sm outline-none focus:border-[#22C55E] bg-white">
                    <option value="">Select crop...</option>
                    {CROPS.map(c => <option key={c} value={c.toLowerCase().replace(/ /g,'_')}>{c}</option>)}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-[#0F1111]">Alert below (GHS/kg)</label>
                  <input type="number" step="0.01" min="0" value={alertForm.threshold}
                    onChange={e => setAlertForm(f => ({...f, threshold: e.target.value}))}
                    placeholder="e.g. 1.50"
                    className="border border-[#888] rounded px-2 py-1.5 text-sm outline-none focus:border-[#22C55E]" />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-[#0F1111]">Your phone (for SMS)</label>
                  <input type="tel" value={alertForm.phone}
                    onChange={e => setAlertForm(f => ({...f, phone: e.target.value}))}
                    placeholder="024 000 0000"
                    className="border border-[#888] rounded px-2 py-1.5 text-sm outline-none focus:border-[#22C55E]" />
                </div>
                <button type="submit" className="bg-[#22C55E] hover:bg-[#16A34A] text-white font-bold rounded py-2 text-xs transition-colors">
                  Save Alert
                </button>
              </form>
            )}

            <div className="divide-y divide-[#EEEEEE]">
              {alerts.length === 0 ? (
                <div className="p-6 text-center">
                  <BellOff className="mx-auto h-8 w-8 text-gray-300 mb-2" />
                  <p className="text-xs text-[#565959]">No price alerts set yet</p>
                </div>
              ) : alerts.map((a, i) => (
                <div key={i} className="px-4 py-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[#0F1111] capitalize">{fmtCrop(a.crop)}</p>
                    <p className="text-xs text-[#565959]">Below GHS {a.threshold_ghs.toFixed(2)}/kg</p>
                    <p className="text-[10px] text-[#AAAAAA]">{a.phone}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => toggleAlert(i)}
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${a.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {a.active ? 'Active' : 'Paused'}
                    </button>
                    <button onClick={() => removeAlert(i)} className="text-gray-300 hover:text-red-500 transition-colors">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick links */}
          <div className="bg-white rounded border border-[#DDDDDD] p-4">
            <h3 className="font-bold text-sm text-[#0F1111] mb-3">Quick Actions</h3>
            <div className="flex flex-col gap-2">
              {[
                { label: 'Browse all listings',   href: '/shop',           icon: ShoppingBag },
                { label: 'Market prices',          href: '/market',         icon: TrendingUp  },
                { label: 'Post a buy request',     href: '/demand',         icon: ArrowRight  },
                { label: 'My reservations',        href: '/shop/cart',      icon: Star        },
              ].map(({ label, href, icon: Icon }) => (
                <Link key={href} href={href}
                  className="flex items-center gap-2 text-sm text-[#007185] hover:text-[#15803D] hover:bg-[#F0FDF4] rounded px-2 py-1.5 transition-colors">
                  <Icon className="h-4 w-4 shrink-0" /> {label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
