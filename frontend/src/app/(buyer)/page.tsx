'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { ArrowRight, MapPin } from 'lucide-react'
import AnimatedStats from '@/components/buyer/AnimatedStats'
import { getAdminRegions, getAdminCrops } from '@/lib/api'
import { cropImageSrc } from '@/lib/cropImage'

// Visual design colors per region — not data, purely UI
const REGION_COLORS: Record<string, { from: string; to: string; accent: string }> = {
  'Ashanti':       { from: '#1D6B3A', to: '#0D3D20', accent: '#4DB876' },
  'Bono':          { from: '#6D28D9', to: '#4C1D95', accent: '#C4B5FD' },
  'Bono East':     { from: '#6D28D9', to: '#4C1D95', accent: '#C4B5FD' },
  'Northern':      { from: '#92400E', to: '#78350F', accent: '#FCD34D' },
  'North East':    { from: '#92400E', to: '#78350F', accent: '#FCD34D' },
  'Savannah':      { from: '#92400E', to: '#78350F', accent: '#FCD34D' },
  'Eastern':       { from: '#0F766E', to: '#134E4A', accent: '#5EEAD4' },
  'Greater Accra': { from: '#1D4ED8', to: '#1E3A8A', accent: '#93C5FD' },
  'Volta':         { from: '#9F1239', to: '#7F1D1D', accent: '#FCA5A5' },
  'Oti':           { from: '#9F1239', to: '#7F1D1D', accent: '#FCA5A5' },
  'Central':       { from: '#0369A1', to: '#0C4A6E', accent: '#7DD3FC' },
  'Western':       { from: '#065F46', to: '#022C22', accent: '#6EE7B7' },
  'Western North': { from: '#065F46', to: '#022C22', accent: '#6EE7B7' },
  'Ahafo':         { from: '#7C3AED', to: '#4C1D95', accent: '#DDD6FE' },
  'Upper East':    { from: '#B45309', to: '#78350F', accent: '#FDE68A' },
  'Upper West':    { from: '#B45309', to: '#78350F', accent: '#FDE68A' },
}
const DEFAULT_COLOR = { from: '#1D6B3A', to: '#0D3D20', accent: '#4DB876' }

interface Region {
  region:         string
  market_count:   number
  district_count: number
}

interface Crop {
  id:                  number
  name:                string
  is_byproduct_source: boolean
}

// ── Hero slideshow config ─────────────────────────────────────────────────────

const HERO_SLIDES = [
  { src: '/crops/onion_4.jpg',    label: 'Onion',    sub: 'Farmers across Ghana'            },
  { src: '/crops/maize_1.jpg',    label: 'Maize',    sub: "Ghana's most traded crop"         },
  { src: '/crops/tomato_1.jpg',   label: 'Tomato',   sub: 'Farm-fresh, market-ready'        },
  { src: '/crops/cassava_1.jpg',  label: 'Cassava',  sub: 'Staple of the nation'            },
  { src: '/crops/rice_1.jpg',     label: 'Rice',     sub: 'Locally grown, freshly harvested'},
  { src: '/crops/plantain_1.jpg', label: 'Plantain', sub: 'From tree to table'              },
]

function HeroSlideshow() {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    const id = setInterval(
      () => setCurrent(c => (c + 1) % HERO_SLIDES.length),
      5000,
    )
    return () => clearInterval(id)
  }, [])

  const slide = HERO_SLIDES[current]

  return (
    <section className="relative overflow-hidden bg-[#071A0E] min-h-[520px] sm:min-h-[600px]">

      {/* Slide images — crossfade */}
      {HERO_SLIDES.map((s, i) => (
        <div
          key={s.src}
          className={`absolute inset-0 transition-opacity duration-[2000ms] ease-in-out hero-slide ${
            i === current ? 'opacity-100 z-10' : 'opacity-0 z-0'
          }`}
        >
          <Image
            src={s.src}
            alt={s.label}
            fill
            className="object-cover"
            style={{ opacity: 0.55 }}
            priority={i === 0}
          />
        </div>
      ))}

      {/* Gradient overlay */}
      <div className="absolute inset-0 z-20 bg-gradient-to-t from-[#071A0E]/90 via-[#071A0E]/40 to-[#071A0E]/20" />

      {/* Hero content */}
      <div className="relative z-30 mx-auto max-w-screen-xl px-6 py-20 flex flex-col items-center text-center gap-6">
        <div className="inline-flex items-center gap-2 rounded-full bg-[#22C55E]/20 border border-[#22C55E]/50 px-4 py-1.5">
          <span className="text-[#4ADE80] text-sm font-semibold">Verified farmers · Real-time prices · Always free</span>
        </div>

        <h1 className="text-3xl sm:text-5xl font-bold text-white leading-tight max-w-2xl drop-shadow-lg">
          Ghana&apos;s <span className="text-[#4ADE80]">Agricultural</span> Marketplace
        </h1>

        <p className="text-white/80 max-w-xl text-base leading-relaxed drop-shadow">
          Buy directly from smallholder farmers with price forecasts,
          climate risk scores, and cooperative logistics.
        </p>

        <div className="flex flex-wrap gap-3 justify-center">
          <Link href="/shop"
            className="rounded bg-[#22C55E] hover:bg-[#16A34A] text-white font-bold px-8 py-3 text-sm transition-colors shadow-lg">
            Shop Now
          </Link>
          <Link href="/shop?view=best"
            className="rounded border-2 border-white/40 hover:border-white/80 bg-white/10 backdrop-blur-sm text-white font-semibold px-8 py-3 text-sm transition-colors">
            Today&apos;s Best Prices
          </Link>
        </div>

        {/* Current crop badge */}
        <div key={current} className="hero-text-in flex items-center gap-2 mt-2">
          <span className="text-[#4ADE80] text-xs font-bold uppercase tracking-widest">
            Now featuring
          </span>
          <span className="bg-white/15 backdrop-blur-sm border border-white/20 text-white text-xs font-semibold px-3 py-1 rounded-full">
            {slide.label} — {slide.sub}
          </span>
        </div>

        {/* Dot indicators */}
        <div className="flex items-center gap-2 mt-1">
          {HERO_SLIDES.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              className={`rounded-full transition-all duration-300 ${
                i === current
                  ? 'bg-[#22C55E] w-6 h-2'
                  : 'bg-white/40 hover:bg-white/70 w-2 h-2'
              }`}
              aria-label={`Slide ${i + 1}`}
            />
          ))}
        </div>
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────────────────────────────────────

const DEALS = [
  { title: 'Fresh Maize — Ashanti Region',    sub: 'Harvest ready · AI price forecast included', badge: "Today's Deal", color: '#F59E0B', href: '/shop?crop=maize'    },
  { title: 'Tomato Surplus — Brong-Ahafo',    sub: 'Perishable — collect within 7 days',          badge: 'Limited Stock', color: '#EF4444', href: '/shop?crop=tomato'   },
  { title: 'Byproducts Marketplace',           sub: 'Maize husks, cassava skins, rice bran',       badge: 'New',           color: '#1D6B3A', href: '/byproducts'         },
]


function CropCard({ crop }: { crop: string }) {
  return (
    <Link href={`/shop?crop=${crop}`}
      className="group flex flex-col items-center gap-2 rounded-lg overflow-hidden hover:shadow-md transition-shadow">
      <div className="w-full aspect-square relative rounded-lg overflow-hidden">
        <Image
          src={cropImageSrc(crop)}
          alt={crop}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-300"
        />
      </div>
      <span className="text-xs font-semibold text-[#0F1111] group-hover:text-[#15803D] transition-colors pb-1">
        {crop.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())}
      </span>
    </Link>
  )
}

export default function BuyerHomePage() {
  const [regions, setRegions] = useState<Region[]>([])
  const [crops,   setCrops]   = useState<Crop[]>([])

  useEffect(() => {
    getAdminRegions()
      .then(r => setRegions(r.data as Region[]))
      .catch(() => {})
    getAdminCrops()
      .then(r => setCrops((r.data as Crop[]).slice(0, 9)))
      .catch(() => {})
  }, [])

  return (
    <div className="flex flex-col gap-0">

      {/* ── Hero ─────────────────────────────────────────────── */}
      <HeroSlideshow />

      {/* ── Deal banners ─────────────────────────────────────── */}
      <section className="bg-[#EAEDED] px-4 py-6">
        <div className="mx-auto max-w-screen-xl grid gap-4 sm:grid-cols-3">
          {DEALS.map(({ title, sub, badge, color, href }) => (
            <Link key={title} href={href}
              className="group relative overflow-hidden rounded-lg bg-white shadow hover:shadow-md transition-shadow p-5 flex flex-col gap-2">
              <span className="inline-block rounded text-white text-xs font-bold px-2 py-0.5 w-fit"
                style={{ backgroundColor: color }}>{badge}</span>
              <h3 className="font-bold text-[#0F1111] text-sm leading-snug group-hover:text-[#15803D] transition-colors">{title}</h3>
              <p className="text-xs text-[#565959]">{sub}</p>
              <span className="mt-auto flex items-center gap-1 text-xs font-semibold text-[#007185] group-hover:text-[#15803D] transition-colors">
                See all <ArrowRight className="h-3 w-3" />
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* ── Shop by crop (from crop_reference table) ─────────── */}
      <section className="bg-white px-4 py-8">
        <div className="mx-auto max-w-screen-xl">
          <h2 className="text-xl font-bold text-[#0F1111] mb-5">Shop by crop</h2>
          {crops.length === 0 ? (
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="animate-pulse flex flex-col items-center gap-2">
                  <div className="w-full aspect-square rounded-lg bg-gray-200" />
                  <div className="h-3 w-16 bg-gray-200 rounded" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
              {crops.map(c => (
                <CropCard key={c.id} crop={c.name} />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ── Browse by region (from ghana_markets table) ──────── */}
      <section className="bg-white px-4 py-8">
        <div className="mx-auto max-w-screen-xl">
          <div className="flex items-baseline justify-between mb-5">
            <h2 className="text-xl font-bold text-[#0F1111]">Browse by region</h2>
            <Link href="/shop" className="text-xs font-semibold text-[#007185] hover:text-[#15803D] transition-colors">
              View all listings
            </Link>
          </div>
          {regions.length === 0 ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-36 rounded-xl bg-gray-200 animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {regions.slice(0, 6).map(r => {
                const c = REGION_COLORS[r.region] ?? DEFAULT_COLOR
                return (
                  <Link key={r.region} href={`/shop?region=${encodeURIComponent(r.region)}`}
                    className="group rounded-xl overflow-hidden hover:shadow-lg transition-all duration-300 hover:-translate-y-0.5">
                    <div className="relative p-5 flex flex-col justify-between h-36 sm:h-40"
                      style={{ background: `linear-gradient(135deg, ${c.from}, ${c.to})` }}>
                      <div className="flex items-start justify-between">
                        <MapPin className="h-4 w-4" style={{ color: c.accent }} />
                        <span className="text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full"
                          style={{ backgroundColor: `${c.accent}25`, color: c.accent }}>
                          {r.market_count} market{r.market_count !== 1 ? 's' : ''}
                        </span>
                      </div>
                      <div>
                        <p className="text-white font-bold text-base sm:text-lg leading-tight mb-0.5">{r.region}</p>
                        <p className="text-xs leading-snug" style={{ color: `${c.accent}CC` }}>
                          {r.district_count} district{r.district_count !== 1 ? 's' : ''}
                        </p>
                      </div>
                      <div className="absolute inset-0 bg-white/0 group-hover:bg-white/5 transition-colors duration-300 rounded-xl" />
                    </div>
                  </Link>
                )
              })}
            </div>
          )}
        </div>
      </section>

      {/* ── Animated trust stats ─────────────────────────────── */}
      <AnimatedStats />

      {/* ── Byproducts CTA ───────────────────────────────────── */}
      <section className="bg-white px-4 py-8">
        <div className="mx-auto max-w-screen-xl">
          <div className="rounded-lg overflow-hidden flex flex-col sm:flex-row items-stretch"
            style={{ background: 'linear-gradient(135deg, #0D3D20, #1D6B3A)' }}>
            <div className="p-8 flex-1">
              <p className="text-[#4DB876] text-xs font-semibold uppercase tracking-widest mb-2">Circular Economy</p>
              <h2 className="text-2xl font-bold text-white mb-2">Waste to Wealth</h2>
              <p className="text-[#7DCFA0] text-sm mb-5 max-w-md">
                Maize husks, cassava skins, rice bran and more — buy agricultural
                byproducts directly from farms at below-market prices.
              </p>
              <Link href="/byproducts"
                className="inline-flex items-center gap-2 bg-[#22C55E] hover:bg-[#16A34A] text-white font-bold text-sm px-6 py-2.5 rounded transition-colors">
                Browse byproducts <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="relative hidden sm:block w-48 h-40 shrink-0 overflow-hidden rounded-lg">
              <Image src="/crops/byproducts.jpg" alt="Agricultural byproducts" fill className="object-cover opacity-80" />
            </div>
          </div>
        </div>
      </section>

    </div>
  )
}
