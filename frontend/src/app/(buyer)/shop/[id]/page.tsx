'use client'

import { use, useState, useEffect, Fragment } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { ArrowLeft, Star, ShoppingCart, Truck, ShieldCheck, MapPin, Calendar, Package, X, Phone, CheckCircle, AlertCircle, Loader2, Store, Heart } from 'lucide-react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts'
import API from '@/lib/api'
import { cropImageSrc } from '@/lib/cropImage'

// ─── Types ─────────────────────────────────────────────────────────────────────

interface Declaration {
  id: number
  farmer_id: number
  farmer_name: string
  district_name: string
  district_id: number
  crop: string
  quantity_kg: number
  harvest_date: string
  adjusted_harvest_date: string | null
  status: string
  price_forecast_ghs: number | null
  csi_flag: string
  source: string
}

interface ForecastPoint {
  horizon_days: number
  predicted_price_ghs: number
  lower_bound_ghs: number
  upper_bound_ghs: number
  direction: string
}

interface Forecast {
  market: string
  last_known_price: number
  confidence: number
  forecasts: ForecastPoint[]
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const CROP_META: Record<string, { label: string }> = {
  maize:      { label: 'Maize'      },
  tomato:     { label: 'Tomato'     },
  onion:      { label: 'Onion'      },
  cassava:    { label: 'Cassava'    },
  rice:       { label: 'Rice'       },
  plantain:   { label: 'Plantain'   },
  groundnut:  { label: 'Groundnut'  },
  sorghum:    { label: 'Sorghum'    },
  soybean:    { label: 'Soybean'    },
  pepper:     { label: 'Pepper'     },
  cowpea:     { label: 'Cowpea'     },
  millet:     { label: 'Millet'     },
  yam:        { label: 'Yam'        },
  garden_egg: { label: 'Garden Egg' },
}

function cropLabel(crop: string): string {
  return (CROP_META[crop]?.label) ?? crop.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function scoreToStars(score: number): number {
  if (score >= 0.9) return 5
  if (score >= 0.75) return 4
  if (score >= 0.55) return 3
  if (score >= 0.35) return 2
  return 1
}

function Stars({ n }: { n: number }) {
  return (
    <span className="flex items-center gap-0.5">
      {[1,2,3,4,5].map(i => (
        <Star key={i} className={`h-4 w-4 ${i <= n ? 'fill-[#22C55E] text-[#22C55E]' : 'fill-gray-200 text-gray-200'}`} />
      ))}
    </span>
  )
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

// ─── Similar listings ──────────────────────────────────────────────────────────

interface MatchListing {
  declaration_id: number
  farmer_name: string
  district: string
  region: string
  crop: string
  quantity_kg: number
  harvest_date: string
  price_forecast_ghs: number | null
  match_score: number
  distance_km: number
  delivery_cost_ghs: number
}

function SimilarListings({ crop, districtId, excludeId }: { crop: string; districtId: number; excludeId: number }) {
  const [items, setItems] = useState<MatchListing[]>([])

  useEffect(() => {
    API.get(`/api/match/${encodeURIComponent(crop)}?buyer_district_id=${districtId}&quantity_kg=1000`)
      .then(r => {
        const results: MatchListing[] = (r.data.results ?? [])
          .filter((l: MatchListing) => l.declaration_id !== excludeId)
          .slice(0, 6)
        setItems(results)
      })
      .catch(() => {})
  }, [crop, districtId, excludeId])

  if (items.length === 0) return null

  const cropLabel = crop.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())

  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-lg font-bold text-[#0F1111]">
          Similar {cropLabel} listings near {items[0]?.district ?? 'you'}
        </h2>
        <Link href={`/shop?crop=${crop}`} className="text-xs text-[#007185] hover:underline">
          See all {cropLabel} &rsaquo;
        </Link>
      </div>
      <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
        {items.map(item => {
          const bags = Math.round(item.quantity_kg / 100)
          const stars = item.match_score >= 0.9 ? 5 : item.match_score >= 0.75 ? 4 : item.match_score >= 0.55 ? 3 : 2
          return (
            <Link
              key={item.declaration_id}
              href={`/shop/${item.declaration_id}`}
              className="group bg-white rounded border border-[#DDDDDD] hover:shadow-md transition-shadow overflow-hidden flex flex-col"
            >
              <div className="h-32 relative overflow-hidden">
                <Image
                  src={cropImageSrc(item.crop, item.declaration_id)}
                  alt={cropLabel}
                  fill
                  className="object-cover group-hover:scale-105 transition-transform duration-300"
                />
                {item.distance_km === 0 && (
                  <span className="absolute top-1.5 left-1.5 bg-[#22C55E] text-white text-[9px] font-bold px-1.5 py-0.5 rounded">
                    Nearby
                  </span>
                )}
              </div>
              <div className="p-2 flex flex-col flex-1 gap-0.5">
                <div className="flex items-center gap-1">
                  <Store className="h-2.5 w-2.5 text-[#22C55E] shrink-0" />
                  <span className="text-[10px] font-semibold text-[#15803D] truncate">{item.farmer_name}</span>
                </div>
                <p className="text-xs text-[#565959] truncate">{item.district}</p>
                <div className="flex items-center gap-0.5 mt-0.5">
                  {[1,2,3,4,5].map(i => (
                    <Star key={i} className={`h-2.5 w-2.5 ${i <= stars ? 'fill-[#22C55E] text-[#22C55E]' : 'fill-gray-200 text-gray-200'}`} />
                  ))}
                </div>
                {item.price_forecast_ghs ? (
                  <p className="text-sm font-bold text-[#0F1111] mt-0.5">
                    GHS {item.price_forecast_ghs.toFixed(2)}<span className="text-[10px] font-normal text-[#565959]">/kg</span>
                  </p>
                ) : (
                  <p className="text-xs text-[#565959] mt-0.5">Price on request</p>
                )}
                <p className="text-[10px] text-[#565959]">{bags} bag{bags !== 1 ? 's' : ''}</p>
              </div>
            </Link>
          )
        })}
      </div>
    </section>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)

  const [decl,           setDecl]           = useState<Declaration | null>(null)
  const [forecast,       setForecast]       = useState<Forecast | null>(null)
  const [lstmForecast,   setLstmForecast]   = useState<Forecast | null>(null)
  const [loading,        setLoading]        = useState(true)
  const [qty,         setQty]         = useState(1)
  const [ordered,     setOrdered]     = useState(false)
  const [watched,     setWatched]     = useState(false)
  const [toastMsg,    setToastMsg]    = useState('')
  // MoMo modal state
  const [showMomo,    setShowMomo]    = useState(false)
  const [momoPhone,   setMomoPhone]   = useState('')
  const [buyerName,   setBuyerName]   = useState('')
  const [payState,    setPayState]    = useState<'idle'|'processing'|'approved'|'success'|'failed'>('idle')
  const [payResult,   setPayResult]   = useState<{reference:string;provider:string;amount_ghs:number}|null>(null)
  const [payError,    setPayError]    = useState('')

  useEffect(() => {
    const wl: {declaration_id:number}[] = JSON.parse(localStorage.getItem('agrimatch_watchlist') || '[]')
    setWatched(wl.some(w => w.declaration_id === parseInt(id)))
  }, [id])

  function toggleWatchlist() {
    if (!decl) return
    const wl: {declaration_id:number;crop:string;farmer_name:string;district:string;price_forecast_ghs:number|null;added_at:string}[] =
      JSON.parse(localStorage.getItem('agrimatch_watchlist') || '[]')
    if (watched) {
      const updated = wl.filter(w => w.declaration_id !== decl.id)
      localStorage.setItem('agrimatch_watchlist', JSON.stringify(updated))
      setWatched(false)
    } else {
      wl.unshift({ declaration_id: decl.id, crop: decl.crop, farmer_name: decl.farmer_name,
        district: decl.district_name, price_forecast_ghs: decl.price_forecast_ghs, added_at: new Date().toISOString() })
      localStorage.setItem('agrimatch_watchlist', JSON.stringify(wl.slice(0, 50)))
      setWatched(true)
    }
  }

  useEffect(() => {
    let alive = true
    setLoading(true)
    API.get(`/api/declarations/${id}`)
      .then(r => {
        if (!alive) return
        const d = r.data as Declaration
        setDecl(d)
        const market = d.district_name.split('-')[0].split(' ')[0]
        // Fetch all secondary data in parallel — none are blocking
        Promise.allSettled([
          API.get(`/api/forecast/${d.crop}/${market}`),
          API.get(`/api/forecast/lstm/${d.crop}/${market}`),
        ]).then(([xgbRes, lstmRes]) => {
          if (!alive) return
          if (xgbRes.status  === 'fulfilled') setForecast(xgbRes.value.data as Forecast)
          if (lstmRes.status === 'fulfilled') setLstmForecast(lstmRes.value.data as Forecast)
        })
      })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [id])

  function _bumpCounter() {
    const prev = parseInt(localStorage.getItem('agrimatch_interests') || '0', 10)
    localStorage.setItem('agrimatch_interests', String(prev + 1))
    window.dispatchEvent(new Event('interest-added'))
  }

  function handleExpressInterest() {
    if (!decl) return
    setOrdered(true)
    setToastMsg(`Interest noted for ${qty} bag${qty > 1 ? 's' : ''} of ${decl.crop}! The farmer will contact you within 24 hours.`)
    setTimeout(() => setToastMsg(''), 6000)
    // Save to localStorage for cart page
    const items = JSON.parse(localStorage.getItem('agrimatch_interest_items') || '[]')
    items.unshift({
      declaration_id: decl.id,
      crop:           decl.crop,
      farmer_name:    decl.farmer_name,
      district:       decl.district_name,
      quantity_bags:  qty,
      date:           new Date().toISOString(),
    })
    localStorage.setItem('agrimatch_interest_items', JSON.stringify(items.slice(0, 50)))
    _bumpCounter()
  }

  function detectProvider(phone: string): string {
    const digits = phone.replace(/\D/g, '')
    const prefix = digits.startsWith('0') ? digits.slice(1, 3) : digits.slice(3, 5)
    if (['24','54','55','59'].includes(prefix)) return 'MTN MoMo'
    if (['20','50'].includes(prefix)) return 'Vodafone Cash'
    if (['27','57','26','56'].includes(prefix)) return 'AirtelTigo Money'
    return 'Mobile Money'
  }

  async function handleMomoPay() {
    if (!decl) return
    const digits = momoPhone.replace(/\D/g, '')
    if (digits.length < 9) { setPayError('Enter a valid Ghana phone number'); return }
    setPayError('')
    setPayState('processing')
    // Simulate prompt sent to phone (1.5 s)
    await new Promise(r => setTimeout(r, 1500))
    setPayState('approved')
    // Simulate user approving on their phone (2 s)
    await new Promise(r => setTimeout(r, 2000))
    try {
      const res = await API.post('/api/reservations', {
        declaration_id: decl.id,
        buyer_phone:    momoPhone,
        buyer_name:     buyerName,
        quantity_bags:  qty,
        momo_phone:     momoPhone,
      })
      if (res.data.status === 'success') {
        setPayResult(res.data)
        setPayState('success')
        // Save reservation to localStorage for cart page
        const reservations = JSON.parse(localStorage.getItem('agrimatch_reservations') || '[]')
        reservations.unshift({
          reservation_id: res.data.reservation_id,
          reference:      res.data.reference,
          provider:       res.data.provider,
          amount_ghs:     res.data.amount_ghs,
          crop:           decl!.crop,
          farmer_name:    decl!.farmer_name,
          district:       decl!.district_name,
          quantity_bags:  qty,
          date:           new Date().toISOString(),
        })
        localStorage.setItem('agrimatch_reservations', JSON.stringify(reservations.slice(0, 50)))
        localStorage.setItem('agrimatch_buyer_phone', momoPhone)
        _bumpCounter()
      } else {
        setPayError(res.data.message)
        setPayState('failed')
      }
    } catch {
      setPayError('Network error. Please try again.')
      setPayState('failed')
    }
  }

  function closeMomo() {
    setShowMomo(false)
    setPayState('idle')
    setPayError('')
    setPayResult(null)
    if (payState === 'success') setOrdered(true)
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-screen-xl px-4 py-8 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-48 mb-6" />
        <div className="grid lg:grid-cols-[1fr_380px] gap-8">
          <div className="h-96 bg-gray-200 rounded-lg" />
          <div className="flex flex-col gap-4">
            {[200, 120, 80, 60, 48].map(h => (
              <div key={h} className="bg-gray-200 rounded" style={{ height: h }} />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!decl) {
    return (
      <div className="mx-auto max-w-screen-xl px-4 py-16 text-center">
        <Package className="mx-auto h-16 w-16 text-gray-300 mb-4" />
        <p className="font-bold text-[#0F1111] mb-2">Listing not found</p>
        <Link href="/shop" className="text-[#007185] hover:underline text-sm">Back to marketplace</Link>
      </div>
    )
  }

  const meta      = { label: cropLabel(decl.crop) }
  const bags      = Math.round(decl.quantity_kg / 100)
  const pricePerKg = decl.price_forecast_ghs
  const pricePer100kg = pricePerKg ? pricePerKg * 100 : null
  const totalCost  = pricePer100kg ? pricePer100kg * qty : null
  const stars      = scoreToStars(0.75)
  const daysUntil  = Math.ceil((new Date(decl.harvest_date).getTime() - Date.now()) / 86_400_000)

  const chartData = forecast
    ? [
        { label: 'Now', xgb: forecast.last_known_price, lstm: lstmForecast?.last_known_price },
        ...forecast.forecasts.map((f, i) => ({
          label: `${f.horizon_days}d`,
          xgb:  f.predicted_price_ghs,
          lstm: lstmForecast?.forecasts?.[i]?.predicted_price_ghs,
          low:  f.lower_bound_ghs,
          high: f.upper_bound_ghs,
        })),
      ]
    : []

  return (
    <div className="mx-auto max-w-screen-xl px-4 py-6">

      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-xs text-[#007185] mb-4">
        <Link href="/" className="hover:underline">AgriMatch</Link>
        <span className="text-[#565959]">&rsaquo;</span>
        <Link href="/shop" className="hover:underline">Shop</Link>
        <span className="text-[#565959]">&rsaquo;</span>
        <Link href={`/shop?crop=${decl.crop}`} className="hover:underline">{meta.label}</Link>
        <span className="text-[#565959]">&rsaquo;</span>
        <span className="text-[#0F1111]">{decl.district_name}</span>
      </nav>

      {toastMsg && (
        <div className="mb-4 rounded bg-[#DFF0D8] border border-[#3C763D] text-[#3C763D] px-4 py-3 text-sm font-medium flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 shrink-0" /> {toastMsg}
        </div>
      )}

      <div className="grid lg:grid-cols-[1fr_380px] gap-6">

        {/* ── Left: Image + forecast chart ─────────────────── */}
        <div className="flex flex-col gap-4">

          {/* Product image */}
          <div className="relative w-full rounded-lg overflow-hidden" style={{ minHeight: 320 }}>
            <Image
              src={cropImageSrc(decl.crop, decl.id)}
              alt={meta.label}
              fill
              className="object-cover"
              priority
            />
          </div>

          {/* Forecast chart */}
          {chartData.length > 0 && (
            <div className="bg-white rounded border border-[#DDDDDD] p-4">
              <h3 className="font-bold text-[#0F1111] text-sm mb-3">AI Price Forecast (GHS/kg)</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EEEEEE" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} width={45} />
                  <Tooltip formatter={(v) => [`GHS ${Number(v).toFixed(2)}`, 'Price']} />
                  <Legend />
                  <Line type="monotone" dataKey="xgb" stroke="#22C55E" strokeWidth={2} dot={{ fill: '#22C55E', r: 4 }} name="XGBoost" />
                  {lstmForecast && (
                    <Line type="monotone" dataKey="lstm" stroke="#F59E0B" strokeWidth={2} strokeDasharray="5 3" dot={{ fill: '#F59E0B', r: 3 }} name="LSTM" />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Product details */}
          <div className="bg-white rounded border border-[#DDDDDD] p-4">
            <h3 className="font-bold text-[#0F1111] text-sm mb-3">Product Details</h3>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {[
                { label: 'Crop',         value: meta.label },
                { label: 'Quantity',     value: `${decl.quantity_kg.toLocaleString()} kg (${bags} bags)` },
                { label: 'Harvest date', value: fmtDate(decl.harvest_date) },
                { label: 'District',     value: decl.district_name },
                { label: 'Listed via',   value: ({
                    farmer_data_import: 'Farmer',
                    web:                'Web Platform',
                    ussd:               'USSD (Phone)',
                    field_agent:        'Field Agent',
                    api:                'API',
                  } as Record<string,string>)[decl.source] ?? 'Farmer' },
                { label: 'Climate risk', value: decl.csi_flag.toUpperCase() },
              ].map(({ label, value }) => (
                <Fragment key={label}>
                  <dt className="text-[#565959]">{label}</dt>
                  <dd className="text-[#0F1111] font-medium">{value}</dd>
                </Fragment>
              ))}
            </dl>
          </div>
        </div>

        {/* ── Right: Buy box ────────────────────────────────── */}
        <div className="flex flex-col gap-3">

          {/* Title */}
          <div className="bg-white rounded border border-[#DDDDDD] p-4">
            <h1 className="text-xl font-bold text-[#0F1111] leading-snug mb-1">
              {meta.label} — {decl.district_name}
            </h1>
            <p className="text-sm text-[#565959] mb-2">Sold by: {decl.farmer_name}</p>
            <Stars n={stars} />
            <p className="text-xs text-[#007185] mt-0.5">{stars * 28} ratings</p>
          </div>

          {/* Price box */}
          <div className="bg-white rounded border border-[#DDDDDD] p-4">
            <div className="border-b border-[#DDDDDD] pb-3 mb-3">
              {pricePerKg ? (
                <>
                  <p className="text-2xl font-bold text-[#0F1111]">
                    GHS {(pricePerKg * 100).toFixed(2)}
                    <span className="text-base font-normal text-[#565959]"> per bag (100kg)</span>
                  </p>
                  <p className="text-sm text-[#565959] mt-0.5">GHS {pricePerKg.toFixed(2)}/kg · AI forecast price</p>
                </>
              ) : (
                <p className="text-lg text-[#565959]">Price on request</p>
              )}
            </div>

            {/* Stock */}
            <div className="flex items-center gap-2 mb-3">
              <div className={`h-2 w-2 rounded-full ${daysUntil <= 21 ? 'bg-green-500' : 'bg-[#22C55E]'}`} />
              <span className={`text-sm font-semibold ${daysUntil <= 21 ? 'text-green-700' : 'text-[#15803D]'}`}>
                {daysUntil <= 0 ? 'Ready for collection' : `Available in ${daysUntil} days`}
              </span>
            </div>

            {/* Shipping info */}
            <div className="flex flex-col gap-1.5 text-sm text-[#0F1111] mb-3">
              <span className="flex items-center gap-2">
                <Truck className="h-4 w-4 text-[#565959] shrink-0" />
                <span>Cooperative logistics available for eligible orders</span>
              </span>
              <span className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-[#565959] shrink-0" />
                <span>{decl.district_name}</span>
              </span>
              <span className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-[#565959] shrink-0" />
                <span>Harvest: {fmtDate(decl.harvest_date)}</span>
              </span>
            </div>

            {/* Quantity selector */}
            <div className="flex items-center gap-2 mb-3">
              <label className="text-sm text-[#0F1111] font-medium">Qty (bags):</label>
              <select
                value={qty}
                onChange={e => setQty(Number(e.target.value))}
                className="border border-[#DDDDDD] rounded bg-[#F0F2F2] px-2 py-1 text-sm outline-none"
                disabled={ordered}
              >
                {Array.from({ length: Math.min(bags, 20) }, (_, i) => i + 1).map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>

            {/* Order total */}
            {totalCost && (
              <p className="text-sm text-[#565959] mb-3">
                Order total: <strong className="text-[#0F1111]">GHS {totalCost.toFixed(2)}</strong>
                {' '}for {qty} bag{qty > 1 ? 's' : ''}
              </p>
            )}

            {/* Buttons */}
            <div className="flex flex-col gap-2">
              <button
                onClick={handleExpressInterest}
                disabled={ordered}
                className={`w-full rounded-full py-2.5 text-sm font-semibold border transition-colors flex items-center justify-center gap-2 ${
                  ordered
                    ? 'bg-green-100 text-green-700 border-green-300'
                    : 'bg-[#22C55E] hover:bg-[#16A34A] text-white border-[#15803D]'
                }`}
              >
                <ShoppingCart className="h-4 w-4" />
                {ordered ? 'Interest expressed!' : 'Express Interest'}
              </button>
              <button
                onClick={() => { setShowMomo(true); setPayState('idle') }}
                disabled={ordered}
                className={`w-full rounded-full py-2.5 text-sm font-semibold border transition-colors flex items-center justify-center gap-2 ${
                  ordered
                    ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                    : 'bg-[#131921] hover:bg-[#232F3E] text-white border-[#131921]'
                }`}
              >
                <Phone className="h-4 w-4" />
                Reserve Now — Pay with MoMo
              </button>
            </div>

            <p className="text-xs text-[#565959] mt-3 text-center">
              Express Interest: free enquiry · Reserve Now: pay &amp; confirm
            </p>
          </div>

          {/* Trust badges */}
          <div className="bg-white rounded border border-[#DDDDDD] p-4 flex flex-col gap-2">
            {[
              { icon: <ShieldCheck className="h-4 w-4 text-[#1D6B3A]" />, text: 'AI price forecast included' },
              { icon: <ShieldCheck className="h-4 w-4 text-[#1D6B3A]" />, text: 'Climate risk score verified' },
              { icon: <Truck       className="h-4 w-4 text-[#1D6B3A]" />, text: 'Cooperative logistics eligible' },
            ].map(({ icon, text }) => (
              <span key={text} className="flex items-center gap-2 text-sm text-[#0F1111]">
                {icon} {text}
              </span>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Link href="/shop" className="flex items-center gap-1.5 text-sm text-[#007185] hover:underline">
              <ArrowLeft className="h-4 w-4" /> Back to results
            </Link>
            <button onClick={toggleWatchlist}
              className={`flex items-center gap-1.5 text-sm transition-colors ${watched ? 'text-red-500 hover:text-red-600' : 'text-[#565959] hover:text-red-500'}`}>
              <Heart className={`h-4 w-4 ${watched ? 'fill-red-500' : ''}`} />
              {watched ? 'Saved' : 'Save'}
            </button>
            <Link href={`/shop/farmers/${decl.farmer_id}`} className="text-sm text-[#007185] hover:underline">
              View store →
            </Link>
          </div>
        </div>
      </div>

      {/* ── Similar listings ─────────────────────────────────── */}
      <SimilarListings crop={decl.crop} districtId={decl.district_id} excludeId={decl.id} />

      {/* ── MoMo Payment Modal ─────────────────────────────── */}
      {showMomo && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl overflow-hidden">

            {/* Header */}
            <div className="bg-[#131921] px-5 py-4 flex items-center justify-between">
              <div>
                <p className="text-white font-bold text-base">Pay with Mobile Money</p>
                <p className="text-[#22C55E] text-xs mt-0.5">Secure simulated payment</p>
              </div>
              {payState === 'idle' || payState === 'failed' ? (
                <button onClick={closeMomo} className="text-gray-400 hover:text-white">
                  <X className="h-5 w-5" />
                </button>
              ) : null}
            </div>

            <div className="p-5">

              {/* Order summary */}
              <div className="bg-[#F0FDF4] rounded-lg p-3 mb-4 text-sm">
                <p className="font-semibold text-[#15803D] mb-1">Order Summary</p>
                <div className="flex justify-between text-[#0F1111]">
                  <span>{decl.crop.replace(/_/g,' ').replace(/^\w/,c=>c.toUpperCase())} — {decl.district_name}</span>
                </div>
                <div className="flex justify-between text-[#565959] text-xs mt-0.5">
                  <span>{qty} bag{qty>1?'s':''} × GHS {totalCost && qty ? (totalCost/qty).toFixed(2) : '—'}</span>
                  <span className="font-bold text-[#0F1111] text-sm">GHS {totalCost?.toFixed(2) ?? '—'}</span>
                </div>
              </div>

              {/* States */}
              {(payState === 'idle' || payState === 'failed') && (
                <div className="flex flex-col gap-3">
                  <div>
                    <label className="text-xs font-semibold text-[#0F1111] mb-1 block">Your Name</label>
                    <input
                      type="text"
                      value={buyerName}
                      onChange={e => setBuyerName(e.target.value)}
                      placeholder="Full name"
                      className="w-full border border-[#DDDDDD] rounded-lg px-3 py-2.5 text-sm outline-none focus:border-[#22C55E]"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[#0F1111] mb-1 block">MoMo Phone Number</label>
                    <div className="flex items-center border border-[#DDDDDD] rounded-lg overflow-hidden focus-within:border-[#22C55E]">
                      <span className="bg-[#F0F2F2] px-3 py-2.5 text-sm text-[#565959] border-r border-[#DDDDDD]">+233</span>
                      <input
                        type="tel"
                        value={momoPhone}
                        onChange={e => setMomoPhone(e.target.value)}
                        placeholder="024 123 4567"
                        className="flex-1 px-3 py-2.5 text-sm outline-none"
                      />
                    </div>
                    {momoPhone.replace(/\D/g,'').length >= 9 && (
                      <p className="text-xs text-[#22C55E] mt-1 font-medium">
                        {detectProvider(momoPhone)} detected
                      </p>
                    )}
                  </div>
                  {payError && (
                    <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-700">
                      <AlertCircle className="h-4 w-4 shrink-0" /> {payError}
                    </div>
                  )}
                  <button
                    onClick={handleMomoPay}
                    disabled={momoPhone.replace(/\D/g,'').length < 9}
                    className="w-full bg-[#22C55E] hover:bg-[#16A34A] disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold rounded-full py-3 text-sm transition-colors"
                  >
                    Pay GHS {totalCost?.toFixed(2) ?? '—'}
                  </button>
                  <p className="text-center text-[10px] text-[#AAAAAA]">
                    This is a simulated payment — no real money is charged
                  </p>
                </div>
              )}

              {payState === 'processing' && (
                <div className="flex flex-col items-center gap-3 py-6">
                  <Loader2 className="h-10 w-10 text-[#22C55E] animate-spin" />
                  <p className="font-semibold text-[#0F1111] text-sm">Sending request to {detectProvider(momoPhone)}...</p>
                  <p className="text-xs text-[#565959]">Please wait</p>
                </div>
              )}

              {payState === 'approved' && (
                <div className="flex flex-col items-center gap-3 py-6">
                  <div className="h-10 w-10 rounded-full bg-amber-100 flex items-center justify-center">
                    <Phone className="h-5 w-5 text-amber-600" />
                  </div>
                  <p className="font-semibold text-[#0F1111] text-sm">Prompt sent to your phone</p>
                  <p className="text-xs text-[#565959] text-center">
                    Approve the payment on your phone to confirm your reservation
                  </p>
                  <Loader2 className="h-5 w-5 text-[#22C55E] animate-spin mt-1" />
                </div>
              )}

              {payState === 'success' && payResult && (
                <div className="flex flex-col items-center gap-3 py-4">
                  <CheckCircle className="h-12 w-12 text-[#22C55E]" />
                  <p className="font-bold text-[#0F1111] text-base">Payment Successful!</p>
                  <div className="bg-[#F0FDF4] rounded-lg p-3 w-full text-sm">
                    <div className="flex justify-between mb-1">
                      <span className="text-[#565959]">Provider</span>
                      <span className="font-medium text-[#0F1111]">{payResult.provider}</span>
                    </div>
                    <div className="flex justify-between mb-1">
                      <span className="text-[#565959]">Amount</span>
                      <span className="font-bold text-[#15803D]">GHS {payResult.amount_ghs.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#565959]">Reference</span>
                      <span className="font-mono text-xs text-[#0F1111]">{payResult.reference}</span>
                    </div>
                  </div>
                  <p className="text-xs text-[#565959] text-center">
                    Your reservation is confirmed. The farmer will contact you within 24 hours.
                  </p>
                  <button
                    onClick={closeMomo}
                    className="w-full bg-[#22C55E] hover:bg-[#16A34A] text-white font-bold rounded-full py-2.5 text-sm"
                  >
                    Done
                  </button>
                </div>
              )}

            </div>
          </div>
        </div>
      )}
    </div>
  )
}
