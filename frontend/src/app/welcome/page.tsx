import Link from 'next/link'
import { Leaf, TrendingUp, Cloud, Truck, Recycle } from 'lucide-react'

// ─── Feature cards ─────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: <TrendingUp className="h-6 w-6 text-[#1D6B3A]" />,
    title: 'Price Forecasts',
    body: '30, 60, and 90-day AI price predictions across 44 Ghana markets using XGBoost and LSTM models.',
  },
  {
    icon: <Cloud className="h-6 w-6 text-[#1D6B3A]" />,
    title: 'Climate Intelligence',
    body: 'Real-time drought stress detection across all 260 Ghana districts using CHIRPS and NASA POWER data.',
  },
  {
    icon: <Truck className="h-6 w-6 text-[#1D6B3A]" />,
    title: 'Cooperative Logistics',
    body: 'Share truck costs automatically with nearby farms going to the same market. Save up to 50% on transport.',
  },
  {
    icon: <Recycle className="h-6 w-6 text-[#1D6B3A]" />,
    title: 'Waste to Wealth',
    body: 'Turn agricultural byproducts — husks, stalks, skins — into additional income streams with instant buyer matching.',
  },
]

// ─── SDG badges ────────────────────────────────────────────────────────────────

const SDGS = [
  { number: '1',  name: 'No Poverty',                       color: '#E5233D' },
  { number: '2',  name: 'Zero Hunger',                      color: '#DDA63A' },
  { number: '8',  name: 'Decent Work & Economic Growth',    color: '#A21942' },
  { number: '12', name: 'Responsible Consumption',          color: '#BF8B2E' },
  { number: '13', name: 'Climate Action',                   color: '#3F7E44' },
]

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#F7FAF8]">

      {/* ── Hero ──────────────────────────────────────────────────── */}
      <section
        className="flex flex-1 flex-col items-center justify-center px-6 py-24 text-center"
        style={{
          background: 'linear-gradient(160deg, #0D3D20 0%, #145228 50%, #1D6B3A 100%)',
          backgroundImage: `
            linear-gradient(160deg, #0D3D20 0%, #145228 50%, #1D6B3A 100%),
            radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)
          `,
          backgroundSize: 'cover, 24px 24px',
        }}
      >
        <div className="mb-5 flex items-center gap-2">
          <Leaf className="h-6 w-6 text-[#4DB876]" strokeWidth={2.5} />
          <span className="font-display text-sm font-semibold tracking-widest text-[#7DCFA0] uppercase">
            AgriMatch
          </span>
        </div>

        <h1 className="font-display mb-5 max-w-3xl text-4xl font-bold leading-tight text-white sm:text-5xl">
          Ghana&apos;s Agricultural<br />Intelligence Platform
        </h1>

        <p className="mb-10 max-w-xl text-base text-[#7DCFA0] leading-relaxed">
          AI-powered price forecasts, crop recommendations, and cooperative logistics
          for smallholder farmers and buyers across Ghana.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/seller"
            className="rounded-xl bg-white px-8 py-3 text-sm font-semibold text-[#1D6B3A] shadow-sm transition-all hover:bg-[#F4FAF6] hover:shadow-md"
          >
            I&apos;m a Farmer
          </Link>
          <Link
            href="/shop"
            className="rounded-xl border-2 border-white/40 px-8 py-3 text-sm font-semibold text-white transition-all hover:border-white/80 hover:bg-white/10"
          >
            I&apos;m a Buyer
          </Link>
        </div>
      </section>

      {/* ── Features strip ───────────────────────────────────────── */}
      <section className="bg-white px-6 py-14">
        <div className="mx-auto max-w-screen-xl">
          <h2 className="font-display mb-10 text-center text-2xl font-bold text-[#0F1613]">
            Built for Ghana&apos;s Smallholder Farmers
          </h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map(({ icon, title, body }) => (
              <div
                key={title}
                className="flex flex-col gap-3 rounded-xl border border-[#C8D8D2] bg-[#F7FAF8] p-5"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#E8F5EE]">
                  {icon}
                </div>
                <h3 className="font-display text-base font-bold text-[#0F1613]">{title}</h3>
                <p className="text-sm leading-relaxed text-[#445E54]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Stats strip ───────────────────────────────────────────── */}
      <section className="bg-[#F4FAF6] px-6 py-10">
        <div className="mx-auto grid max-w-screen-xl grid-cols-2 gap-6 text-center sm:grid-cols-4">
          {[
            { value: '265', label: 'XGBoost price models'    },
            { value: '44',  label: 'Ghana markets covered'   },
            { value: '260', label: 'Districts monitored'     },
            { value: '16',  label: 'Crop types supported'    },
          ].map(({ value, label }) => (
            <div key={label}>
              <p className="font-display text-3xl font-bold text-[#1D6B3A]">{value}</p>
              <p className="mt-1 text-sm text-[#445E54]">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── SDG strip ─────────────────────────────────────────────── */}
      <section className="bg-white px-6 py-12">
        <div className="mx-auto max-w-screen-xl">
          <p className="mb-6 text-center text-xs font-semibold uppercase tracking-widest text-[#7A9088]">
            Contributing to the UN Sustainable Development Goals
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            {SDGS.map(({ number, name, color }) => (
              <div
                key={number}
                className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-white text-sm font-semibold"
                style={{ backgroundColor: color }}
              >
                <span className="font-display text-xl font-black leading-none">{number}</span>
                <span className="max-w-[120px] text-xs font-medium leading-tight">{name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────── */}
      <footer className="border-t border-[#C8D8D2] bg-[#F7FAF8] px-6 py-8">
        <div className="mx-auto max-w-screen-xl flex flex-col items-center gap-4 text-center sm:flex-row sm:justify-between sm:text-left">
          <div>
            <div className="flex items-center gap-1.5 justify-center sm:justify-start">
              <Leaf className="h-4 w-4 text-[#1D6B3A]" />
              <span className="font-display text-sm font-bold text-[#1D6B3A]">AgriMatch</span>
            </div>
            <p className="mt-0.5 text-xs text-[#7A9088]">
              Predictive Agricultural Intelligence Platform
            </p>
            <p className="text-xs text-[#7A9088]">Built for Ghana&apos;s smallholder farmers</p>
          </div>

          <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-[#445E54] sm:justify-end">
            {[
              { href: '/seller',     label: 'Farmer'     },
              { href: '/shop',       label: 'Buyer'      },
              { href: '/byproducts', label: 'Byproducts' },
              { href: '/admin',      label: 'Admin'      },
            ].map(({ href, label }) => (
              <Link key={href} href={href} className="hover:text-[#1D6B3A] transition-colors">
                {label}
              </Link>
            ))}
          </nav>
        </div>
      </footer>

    </div>
  )
}
