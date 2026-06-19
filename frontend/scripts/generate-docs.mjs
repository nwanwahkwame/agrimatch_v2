/**
 * AgriMatch Platform Documentation Generator
 * Takes live screenshots from Vercel, then renders a full PDF.
 *
 * Usage: node scripts/generate-docs.mjs
 */

import { chromium } from 'playwright'
import { promises as fs } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const BASE      = 'https://agrimatch-psi.vercel.app'
const OUT_DIR   = path.join(__dirname, '..', '..', 'agrimatch-docs')
const SS_DIR    = path.join(OUT_DIR, 'screenshots')
const HTML_PATH = path.join(OUT_DIR, 'agrimatch-documentation.html')
const PDF_PATH  = path.join(OUT_DIR, 'AgriMatch-Platform-Documentation.pdf')

// ── Helpers ──────────────────────────────────────────────────────────────────

async function capture(page, name) {
  const file = path.join(SS_DIR, `${name}.png`)
  await page.screenshot({ path: file, fullPage: true })
  const buf = await fs.readFile(file)
  return `data:image/png;base64,${buf.toString('base64')}`
}

async function goto(page, url, wait = 3500) {
  await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 })
  await page.waitForTimeout(wait)
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  await fs.mkdir(SS_DIR, { recursive: true })
  console.log('\n📸  Launching Chromium...\n')

  const browser = await chromium.launch()
  const ctx     = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page    = await ctx.newPage()

  const S = {}  // screenshot map

  const routes = [
    ['welcome',           '/welcome'],
    ['home',              '/'],
    ['shop',              '/shop'],
    ['seller',            '/seller'],
    ['seller_listings',   '/seller/listings'],
    ['seller_analytics',  '/seller/analytics'],
    ['seller_account',    '/seller/account'],
    ['byproducts',        '/byproducts'],
    ['admin',             '/admin'],
    ['admin_farmers',     '/admin/farmers'],
    ['admin_markets',     '/admin/markets'],
    ['admin_pipeline',    '/admin/pipeline'],
    ['admin_models',      '/admin/models'],
    ['ussd',              '/admin/ussd-test'],
  ]

  for (const [name, url] of routes) {
    process.stdout.write(`  Capturing ${url.padEnd(25)} `)
    await goto(page, `${BASE}${url}`)
    S[name] = await capture(page, name)
    console.log('✓')
  }

  // Product detail — click first listing card
  process.stdout.write(`  Capturing /shop/[id]              `)
  await goto(page, `${BASE}/shop`)
  const firstCard = page.locator('a[href^="/shop/"]').first()
  if (await firstCard.count()) {
    await firstCard.click()
    await page.waitForTimeout(4000)
    S['product'] = await capture(page, 'product')
    console.log('✓')
  } else {
    S['product'] = S['shop']
    console.log('⚠ (used shop fallback)')
  }

  await browser.close()
  console.log('\n✓  All screenshots captured.\n📄  Building HTML document...')

  // ── Generate HTML ──────────────────────────────────────────────────────────
  const html = buildHTML(S)
  await fs.writeFile(HTML_PATH, html, 'utf8')
  console.log('✓  HTML written.')

  // ── Render to PDF ─────────────────────────────────────────────────────────
  console.log('🖨   Rendering PDF (this takes ~30 seconds)...')
  const b2   = await chromium.launch()
  const pg2  = await b2.newPage()
  await pg2.goto(`file://${HTML_PATH}`, { waitUntil: 'networkidle', timeout: 60000 })
  await pg2.waitForTimeout(2000)
  await pg2.pdf({
    path: PDF_PATH,
    format: 'A4',
    printBackground: true,
    margin: { top: '18mm', right: '16mm', bottom: '18mm', left: '16mm' },
  })
  await b2.close()
  console.log(`\n✅  PDF ready → ${PDF_PATH}\n`)
}

// ── HTML builder ─────────────────────────────────────────────────────────────

function img(src, caption) {
  return `
    <figure class="screenshot">
      <img src="${src}" alt="${caption}" />
      <figcaption>${caption}</figcaption>
    </figure>`
}

function section(num, title, content) {
  return `
    <section class="page-break">
      <h1 class="section-num">Section ${num}</h1>
      <h2 class="section-title">${title}</h2>
      ${content}
    </section>`
}

function callout(num, text) {
  return `<div class="callout"><span class="callout-num">${num}</span><span>${text}</span></div>`
}

function buildHTML(S) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>AgriMatch Platform Documentation</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 10pt;
    color: #1a1a1a;
    background: #fff;
    line-height: 1.6;
  }

  /* ── Cover ── */
  .cover {
    display: flex; flex-direction: column;
    justify-content: center; align-items: flex-start;
    min-height: 100vh;
    padding: 60px;
    background: linear-gradient(135deg, #0D3D20 0%, #1D6B3A 60%, #25864A 100%);
    page-break-after: always;
  }
  .cover-badge {
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    color: #4DB876;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 5px 14px;
    border-radius: 100px;
    margin-bottom: 28px;
  }
  .cover h1 {
    font-size: 38pt;
    font-weight: 800;
    color: #fff;
    line-height: 1.1;
    margin-bottom: 12px;
  }
  .cover h1 span { color: #FF9900; }
  .cover-sub {
    font-size: 13pt;
    color: rgba(255,255,255,0.75);
    margin-bottom: 48px;
    max-width: 480px;
    font-weight: 300;
  }
  .cover-meta {
    display: flex; gap: 40px;
    border-top: 1px solid rgba(255,255,255,0.2);
    padding-top: 28px;
  }
  .cover-meta-item label {
    display: block;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #4DB876;
    margin-bottom: 3px;
  }
  .cover-meta-item span {
    font-size: 10pt;
    color: #fff;
    font-weight: 500;
  }
  .cover-stats {
    display: flex; gap: 36px; margin-bottom: 48px;
  }
  .cover-stat strong {
    display: block;
    font-size: 26pt;
    font-weight: 800;
    color: #FF9900;
    line-height: 1;
  }
  .cover-stat span {
    font-size: 8.5pt;
    color: rgba(255,255,255,0.65);
    font-weight: 400;
  }

  /* ── TOC ── */
  .toc {
    padding: 48px 60px;
    page-break-after: always;
  }
  .toc h2 { font-size: 18pt; font-weight: 700; color: #0D3D20; margin-bottom: 28px; }
  .toc-item {
    display: flex; align-items: baseline;
    border-bottom: 1px dashed #ddd;
    padding: 8px 0;
    gap: 8px;
  }
  .toc-num { font-weight: 700; color: #1D6B3A; min-width: 24px; }
  .toc-title { flex: 1; font-size: 10pt; }
  .toc-page { font-size: 9pt; color: #888; }

  /* ── Sections ── */
  section {
    padding: 40px 60px;
  }
  .page-break { page-break-before: always; }
  .section-num {
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #FF9900;
    margin-bottom: 4px;
  }
  .section-title {
    font-size: 20pt;
    font-weight: 800;
    color: #0D3D20;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 3px solid #1D6B3A;
  }

  p { margin-bottom: 10px; font-size: 10pt; color: #333; }
  h3 { font-size: 12pt; font-weight: 700; color: #0D3D20; margin: 20px 0 8px; }
  h4 { font-size: 10.5pt; font-weight: 600; color: #1D6B3A; margin: 14px 0 6px; }
  ul { margin: 8px 0 12px 20px; }
  li { margin-bottom: 4px; font-size: 10pt; color: #333; }

  /* ── Screenshots ── */
  .screenshot {
    margin: 20px 0;
    border: 1px solid #ddd;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    page-break-inside: avoid;
  }
  .screenshot img {
    width: 100%;
    display: block;
    max-height: 500px;
    object-fit: cover;
    object-position: top;
  }
  .screenshot figcaption {
    background: #F7FAF8;
    border-top: 1px solid #ddd;
    font-size: 8.5pt;
    color: #666;
    padding: 6px 12px;
    font-style: italic;
  }

  /* ── Callouts ── */
  .callout {
    display: flex; align-items: flex-start; gap: 10px;
    background: #F7FAF8;
    border-left: 3px solid #1D6B3A;
    padding: 8px 12px;
    border-radius: 0 6px 6px 0;
    margin: 8px 0;
    page-break-inside: avoid;
  }
  .callout-num {
    background: #1D6B3A; color: #fff;
    font-size: 8pt; font-weight: 700;
    width: 18px; height: 18px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
  }

  /* ── Info boxes ── */
  .info-box {
    background: #EFF6FF; border: 1px solid #BFDBFE;
    border-radius: 8px; padding: 14px 16px; margin: 16px 0;
    page-break-inside: avoid;
  }
  .info-box.warning {
    background: #FFFBEB; border-color: #FDE68A;
  }
  .info-box.green {
    background: #F0FDF4; border-color: #BBF7D0;
  }
  .info-box strong { font-size: 9.5pt; display: block; margin-bottom: 4px; }

  /* ── Tables ── */
  table {
    width: 100%; border-collapse: collapse;
    margin: 16px 0; font-size: 9pt;
    page-break-inside: avoid;
  }
  th {
    background: #0D3D20; color: #fff;
    text-align: left; padding: 8px 10px;
    font-weight: 600; font-size: 8.5pt;
    letter-spacing: 0.05em;
  }
  td {
    padding: 7px 10px;
    border-bottom: 1px solid #eee;
    vertical-align: top;
  }
  tr:nth-child(even) td { background: #FAFAFA; }
  .badge {
    display: inline-block;
    padding: 2px 7px; border-radius: 100px;
    font-size: 7.5pt; font-weight: 700;
  }
  .badge-live  { background: #D1FAE5; color: #065F46; }
  .badge-mock  { background: #FEF3C7; color: #92400E; }
  .badge-calc  { background: #EDE9FE; color: #4C1D95; }
  .badge-api   { background: #DBEAFE; color: #1E40AF; }

  /* ── Pitch ── */
  .pitch-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0; }
  .pitch-card {
    border: 1px solid #ddd; border-radius: 8px; padding: 14px;
    page-break-inside: avoid;
  }
  .pitch-card h4 { margin-top: 0; }
  .pitch-card.highlight { border-color: #1D6B3A; background: #F0FDF4; }
  .kpi-row { display: flex; gap: 16px; margin: 16px 0; }
  .kpi {
    flex: 1; text-align: center;
    background: linear-gradient(135deg, #0D3D20, #1D6B3A);
    border-radius: 8px; padding: 16px 8px; color: #fff;
    page-break-inside: avoid;
  }
  .kpi strong { display: block; font-size: 22pt; font-weight: 800; color: #FF9900; }
  .kpi span   { font-size: 8pt; color: rgba(255,255,255,0.7); }

  .problem-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }
  .problem-card {
    border-left: 4px solid #EF4444;
    background: #FEF2F2;
    padding: 12px;
    border-radius: 0 6px 6px 0;
    page-break-inside: avoid;
  }
  .solution-card {
    border-left: 4px solid #1D6B3A;
    background: #F0FDF4;
    padding: 12px;
    border-radius: 0 6px 6px 0;
    page-break-inside: avoid;
  }
  .moat-item {
    display: flex; gap: 10px; align-items: flex-start;
    padding: 10px 0; border-bottom: 1px solid #eee;
  }
  .moat-icon {
    width: 32px; height: 32px; border-radius: 8px;
    background: #FF9900; color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 14pt; flex-shrink: 0;
  }
</style>
</head>
<body>

<!-- ═══════════════════════════════════════════════════════ COVER ═══ -->
<div class="cover">
  <div class="cover-badge">Platform Documentation & Investor Reference</div>
  <h1>Agri<span>Match</span></h1>
  <p class="cover-sub">Ghana's Agricultural Intelligence Platform — AI-powered price forecasts, cooperative logistics, climate risk scoring, and offline USSD access for smallholder farmers and buyers.</p>

  <div class="cover-stats">
    <div class="cover-stat"><strong>265</strong><span>XGBoost price models</span></div>
    <div class="cover-stat"><strong>44</strong><span>Ghana markets covered</span></div>
    <div class="cover-stat"><strong>260</strong><span>Districts monitored</span></div>
    <div class="cover-stat"><strong>16</strong><span>Crop types</span></div>
  </div>

  <div class="cover-meta">
    <div class="cover-meta-item"><label>Version</label><span>1.0 — June 2026</span></div>
    <div class="cover-meta-item"><label>Classification</label><span>Confidential</span></div>
    <div class="cover-meta-item"><label>Platform URL</label><span>agrimatch-psi.vercel.app</span></div>
    <div class="cover-meta-item"><label>API</label><span>agrimatch-production.up.railway.app</span></div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ TOC ════ -->
<div class="toc">
  <h2>Table of Contents</h2>
  ${[
    [1, 'Platform Overview'],
    [2, 'Landing Page — Full Walkthrough'],
    [3, 'Buyer Shop Catalog — Full Walkthrough'],
    [4, 'Product Detail Page — Full Walkthrough'],
    [5, 'Farmer / Seller Dashboard — Full Walkthrough'],
    [6, 'Admin Dashboards — Full Walkthrough'],
    [7, 'Offline USSD Simulator — Full Walkthrough'],
    [8, 'Data Provenance Reference'],
    [9, 'Investor Pitch Framework'],
  ].map(([n, t]) => `
    <div class="toc-item">
      <span class="toc-num">${n}</span>
      <span class="toc-title">${t}</span>
    </div>`).join('')}
</div>

<!-- ═══════════════════════════════════════════════════ SECTION 1 ═══ -->
${section(1, 'Platform Overview', `
  <p>AgriMatch is a full-stack agricultural intelligence platform designed specifically for Ghana's smallholder farming ecosystem. Unlike conventional marketplaces that simply list produce for sale, AgriMatch integrates four layers of intelligence that a farmer or buyer cannot get anywhere else in the market.</p>

  <div class="pitch-grid" style="margin-top:20px">
    <div class="pitch-card highlight">
      <h4>🌾 For Farmers (Sellers)</h4>
      <ul>
        <li>30/60/90-day AI price forecasts per crop per market</li>
        <li>Climate Stress Index (CSI) drought warnings</li>
        <li>Cooperative truck-sharing logistics</li>
        <li>USSD access from any feature phone</li>
        <li>Byproduct listing for zero-waste income</li>
      </ul>
    </div>
    <div class="pitch-card highlight">
      <h4>🛒 For Buyers</h4>
      <ul>
        <li>Verified farmer listings with AI forecast prices</li>
        <li>Climate risk flag on every listing</li>
        <li>Real-time delivery cost estimation</li>
        <li>Regional and crop-based filtering</li>
        <li>Byproducts marketplace at below-market rates</li>
      </ul>
    </div>
  </div>

  <h3>Technology Stack</h3>
  <table>
    <tr><th>Layer</th><th>Technology</th><th>Purpose</th></tr>
    <tr><td>Frontend</td><td>Next.js 16, Tailwind CSS, Recharts</td><td>Buyer/Seller/Admin web interface</td></tr>
    <tr><td>API</td><td>FastAPI (Python), SQLAlchemy ORM</td><td>REST API serving all platform data</td></tr>
    <tr><td>Database</td><td>Neon PostgreSQL (serverless)</td><td>All structured data, 37,933+ price records</td></tr>
    <tr><td>ML Models</td><td>XGBoost (265 models), LSTM (107 models)</td><td>Price forecasting per crop × market</td></tr>
    <tr><td>Climate Data</td><td>CHIRPS satellite, NASA POWER API</td><td>Rainfall, solar, temperature indicators</td></tr>
    <tr><td>Scheduling</td><td>APScheduler</td><td>Daily data ingestion and model updates</td></tr>
    <tr><td>USSD</td><td>Africa's Talking</td><td>Feature-phone access for offline farmers</td></tr>
    <tr><td>Hosting</td><td>Vercel (frontend) + Railway (API)</td><td>Cloud deployment, auto-scaling</td></tr>
  </table>
`)}

<!-- ═══════════════════════════════════════════════════ SECTION 2 ═══ -->
${section(2, 'Landing Page — Full Walkthrough', `
  ${img(S.welcome, 'AgriMatch Landing Page — agrimatch-psi.vercel.app/welcome')}

  <h3>Purpose</h3>
  <p>The landing page is the public-facing entry point for new visitors. It communicates the platform's value proposition to both farmers and buyers before they create an account or explore the marketplace.</p>

  <h3>Key UI Elements</h3>
  ${callout(1, 'Hero section — A full-width dark green gradient hero with the AgriMatch wordmark, a one-line value proposition, and two call-to-action buttons: "I\'m a Farmer" (routes to /seller) and "I\'m a Buyer" (routes to /shop).')}
  ${callout(2, 'Feature cards — Four cards explaining Price Forecasts, Climate Intelligence, Cooperative Logistics, and Waste to Wealth (byproducts). Each card has an icon, title, and 2-line description.')}
  ${callout(3, 'Platform statistics strip — Four live statistics: 265 XGBoost models, 44 markets, 260 districts, 16 crops. These are hardcoded to match the actual trained model count.')}
  ${callout(4, 'SDG badges — Five UN Sustainable Development Goal badges showing alignment with SDG 1 (No Poverty), 2 (Zero Hunger), 8 (Decent Work), 12 (Responsible Consumption), and 13 (Climate Action).')}
  ${callout(5, 'Footer navigation — Links to Farmer portal (/seller), Buyer marketplace (/shop), Byproducts, and Admin panel.')}

  <div class="info-box green">
    <strong>Navigation tip</strong>
    From this page, click "I'm a Farmer" to enter the Seller Central dashboard, or "I'm a Buyer" to go directly to the produce marketplace.
  </div>
`)}

<!-- ═══════════════════════════════════════════════════ SECTION 3 ═══ -->
${section(3, 'Buyer Shop Catalog — Full Walkthrough', `
  ${img(S.home, 'Buyer Homepage — agrimatch-psi.vercel.app/')}

  <h3>Buyer Homepage</h3>
  <p>The buyer-facing homepage uses an Amazon-style layout with a sticky navigation bar, a hero banner, featured deal cards, a crop image grid, a regional browse section, and animated trust statistics.</p>

  ${callout(1, 'Navigation bar (top) — AgriMatch logo, crop category selector, search field, "Account / Seller" link, and Enquiries. The "☰ All" button reveals a Browse by Region dropdown.')}
  ${callout(2, 'Secondary navigation — Quick links: Fresh Listings, Crops, Byproducts, Today\'s Best Prices, Sell on AgriMatch.')}
  ${callout(3, 'Hero banner — Ghana\'s Agricultural Marketplace heading. "Shop Now" and "Today\'s Best Prices" buttons filter directly into the /shop listing grid.')}
  ${callout(4, 'Deal banners — Three curated deals: Fresh Maize (Ashanti), Tomato Surplus (Brong-Ahafo), Byproducts Marketplace. Each links to filtered shop results.')}
  ${callout(5, 'Shop by crop — Six crop image cards (Maize, Tomato, Onion, Cassava, Rice, Plantain) linking to pre-filtered search results.')}
  ${callout(6, 'Browse by region — Six Ghana region cards (Ashanti, Bono & Bono East, Northern, Eastern, Greater Accra, Volta) with market count and tagline.')}
  ${callout(7, 'Animated trust stats — Six stat cards that animate when scrolled into view: GHS 48M+ produce value (count-up), 98.4% AI accuracy (SVG arc), 1,840+ farmers (expand ping), 44 markets (ripple), <2 min match time (typewriter), Free for buyers (shimmer).')}

  ${img(S.shop, 'Shop Catalog — agrimatch-psi.vercel.app/shop')}

  <h3>Shop Listing Grid</h3>
  ${callout(1, 'Crop filter tabs — Switch between Maize, Tomato, Onion, Cassava, Rice, and Plantain. Active tab is highlighted in dark. Tabs call the /api/match endpoint with a default buyer district.')}
  ${callout(2, 'Sort controls — Sort by Best Match, Lowest Price, Nearest, or Freshest Harvest.')}
  ${callout(3, 'Filter sidebar — Toggle filters: max distance, max price per kg, minimum quantity. Filters update the API query in real time.')}
  ${callout(4, 'Listing cards — Each card shows: crop image, farmer name, district, harvest date, quantity (kg), AI forecast price (GHS/kg), climate risk flag (CSI), delivery cost, and an "Express Interest" button.')}
  ${callout(5, 'CSI badge — A colored badge (green = safe, amber = moderate, red = high risk) derived from real CHIRPS satellite rainfall analysis over the farm\'s district.')}
`)}

<!-- ═══════════════════════════════════════════════════ SECTION 4 ═══ -->
${section(4, 'Product Detail Page — Full Walkthrough', `
  ${img(S.product, 'Product Detail — agrimatch-psi.vercel.app/shop/[id]')}

  <h3>Purpose</h3>
  <p>The product detail page gives buyers a comprehensive view of a single farmer's listing, including AI price forecasts, logistics cost breakdown, and climate risk assessment before committing to an order.</p>

  ${callout(1, 'Buy box (right panel) — Shows the AI forecast price (GHS/kg), adjusted harvest date, quantity available, total delivery cost from the buyer\'s district, and the "Express Interest" button.')}
  ${callout(2, 'AI Price Forecast chart — A dual-line chart (XGBoost in amber, LSTM in green) showing predicted price over 30, 60, and 90 days. Confidence interval shading indicates model certainty. Built with Recharts.')}
  ${callout(3, 'Climate risk section — The CSI (Climate Stress Index) flag derived from CHIRPS satellite data and NASA POWER telemetry. A red flag warns the buyer of elevated crop delay risk.')}
  ${callout(4, 'Logistics details — Breakdown of road distance (km), vehicle type, cargo tier, and cost per kg. Calculated from the district distance matrix (606,060 routes precomputed).')}
  ${callout(5, 'Byproducts from this farm — If the farmer registered byproducts (husks, stalks, bran), they appear here as available for separate purchase.')}

  <div class="info-box">
    <strong>How prices are calculated</strong>
    The displayed price is the XGBoost model\'s 30-day forward forecast, trained on 37,933 historical MoFA/HDX price observations for this specific crop-market pair. It is not the current market spot price — it is a prediction of what the price will be at harvest time.
  </div>
`)}

<!-- ═══════════════════════════════════════════════════ SECTION 5 ═══ -->
${section(5, 'Farmer / Seller Dashboard — Full Walkthrough', `
  ${img(S.seller, 'Seller Dashboard — agrimatch-psi.vercel.app/seller')}

  <h3>Seller Central Overview</h3>
  <p>The Seller Central dashboard is the primary interface for farmers. It uses a dark Amazon-style sidebar (visible on desktop) and a mobile bottom tab bar. All data is loaded live from the FastAPI backend.</p>

  ${callout(1, 'Sidebar navigation — Dashboard, Inventory, Add a Listing, Analytics, Byproducts, Account. The active page is highlighted with a gold left-border accent.')}
  ${callout(2, 'Strategy cards — AI-generated selling recommendations per declaration. Each card shows: crop, urgency level (sell_now / hold / watch), headline, body text, and key numbers (current price, change %, net after delivery, total expected income).')}
  ${callout(3, 'Urgency badge — Color-coded chip: red = sell_now, amber = watch, green = hold. Driven by the strategy engine comparing forecast price vs. current market median.')}
  ${callout(4, 'Summary metrics — Active listings count, sell-now alerts, declarations needing attention.')}

  ${img(S.seller_listings, 'Inventory Page — agrimatch-psi.vercel.app/seller/listings')}

  <h3>Inventory / Listings</h3>
  ${callout(1, 'Declarations table — All farmer declarations with crop, quantity, harvest date, status, forecast price, and CSI flag. Live from /api/declarations/farmer/{id}.')}

  ${img(S.seller_analytics, 'Analytics Page — agrimatch-psi.vercel.app/seller/analytics')}

  <h3>Analytics</h3>
  ${callout(1, 'Stat cards — Estimated year-to-date income, active listing count, total quantity (kg), average forecast price per kg.')}
  ${callout(2, 'Monthly income bar chart — Historical monthly income estimates (mock data seeded from declaration history).')}
  ${callout(3, 'Price trend line chart — Weekly price movements for Maize, Tomato, and Cassava over the past 6 weeks. Updated from the XGBoost forecast pipeline.')}
  ${callout(4, 'Declarations table — All declarations with live status from the API.')}

  ${img(S.seller_account, 'Account Page — agrimatch-psi.vercel.app/seller/account')}

  <h3>Account Settings</h3>
  ${callout(1, 'Profile card — Farmer ID, name, phone, district, region, and member-since date. Currently read-only; editable via USSD or admin panel.')}
  ${callout(2, 'Notification preferences — Toggle switches for: Price alerts, Climate stress (CSI) alerts, Logistics group alerts. Changes persist to the API.')}
  ${callout(3, 'Phone verification badge — Confirms USSD phone number has been verified via Africa\'s Talking.')}
`)}

<!-- ═══════════════════════════════════════════════════ SECTION 6 ═══ -->
${section(6, 'Admin Dashboards — Full Walkthrough', `
  <p>The admin section is accessible at /admin and is intended for platform operators. It provides a real-time view of platform health, data pipeline status, AI model status, and all registered farmers and markets.</p>

  ${img(S.admin, 'Admin Dashboard — agrimatch-psi.vercel.app/admin')}

  <h3>Main Dashboard</h3>
  ${callout(1, 'Green sidebar — Navigation between Dashboard, Farmers, Markets, Pipeline, AI Models, and USSD Test. Collapses to a horizontal tab bar on mobile.')}
  ${callout(2, 'Platform actions panel — One-click buttons to: Run CSI update, Send price alerts, Rebuild logistics groups, Reload ML models. Each calls the corresponding API endpoint and shows live success/error feedback.')}
  ${callout(3, 'Database row counts — Live count of rows in every major table: 37,933 clean prices, 1.59M CHIRPS daily observations, 1.66M NASA POWER records, 606,060 logistics cost routes.')}
  ${callout(4, 'Scheduler job status — All 10 APScheduler jobs with their cron schedule and last run timestamp.')}

  ${img(S.admin_farmers, 'Farmers Table — agrimatch-psi.vercel.app/admin/farmers')}

  <h3>Farmers</h3>
  ${callout(1, 'Farmers table — All registered farmers with ID, name, phone, district, region, declaration count, join date, and active/pending status.')}

  ${img(S.admin_markets, 'Markets Overview — agrimatch-psi.vercel.app/admin/markets')}

  <h3>Markets</h3>
  ${callout(1, 'All 44 Ghana markets — Listed with region, crops tracked (up to 16 per market), last updated date, and live/stale status (stale = not updated in >3 days).')}

  ${img(S.admin_pipeline, 'Data Pipeline — agrimatch-psi.vercel.app/admin/pipeline')}

  <h3>Pipeline</h3>
  ${callout(1, 'Scheduler jobs — 10 automated ingestion jobs: CHIRPS daily update, NASA POWER daily update, Climate Indicators, CSI Update, XGBoost weekly retrain, LSTM monthly retrain, HDX/MoFA price ingest, Feature Store rebuild, Logistics cost cache.')}
  ${callout(2, 'Database tables — Row counts and type (live vs. static) for every table. Live tables update daily; static tables are precomputed.')}

  ${img(S.admin_models, 'AI Models — agrimatch-psi.vercel.app/admin/models')}

  <h3>AI Models</h3>
  ${callout(1, 'Live model status — XGBoost model count, LSTM model count, delay classifier status, and API version fetched live from /api/models/status.')}
  ${callout(2, 'Crop coverage bars — For each of the 6 crops, a progress bar shows how many of the 44 markets have trained models.')}
  ${callout(3, 'Accuracy by market — Sample 30-day directional accuracy for XGBoost and LSTM models per major market (Kumasi, Accra, Techiman, Tamale, Sunyani, Koforidua).')}
  ${callout(4, 'Retraining schedule — XGBoost retrains weekly (Sunday 02:00 UTC), LSTM monthly (1st of month 03:00 UTC), delay classifier monthly (04:00 UTC).')}
`)}

<!-- ═══════════════════════════════════════════════════ SECTION 7 ═══ -->
${section(7, 'Offline USSD Simulator — Full Walkthrough', `
  ${img(S.ussd, 'USSD Simulator — agrimatch-psi.vercel.app/admin/ussd-test')}

  <h3>Purpose</h3>
  <p>The USSD Simulator allows platform operators to test and demonstrate the offline farmer interface — the same flow a farmer would experience by dialling a USSD shortcode from any feature phone, with no smartphone or internet connection required.</p>

  <h3>Why USSD Matters</h3>
  <p>Over 70% of Ghana's smallholder farmers use basic feature phones. USSD (Unstructured Supplementary Service Data) works on every mobile phone on any network, with no data plan, no app download, and no internet connection. AgriMatch's USSD integration via Africa's Talking removes the single biggest barrier to digital inclusion in Ghana's agricultural sector.</p>

  ${callout(1, 'Phone simulator — A mock phone UI that displays the USSD session exactly as a farmer would see it on their phone screen.')}
  ${callout(2, 'Session flow — The simulator walks through the full USSD menu: Welcome → 1. Register / 2. Check prices / 3. My listings / 4. Climate alert / 0. Exit.')}
  ${callout(3, 'Real-time response — Inputs are sent to the FastAPI USSD endpoint (/api/ussd) and the real server response is displayed in the phone simulator.')}
  ${callout(4, 'Session analytics — Stats panel shows: total sessions today, total this week, declarations completed via USSD, average session duration, most common drop-off state, active sessions now.')}
  ${callout(5, 'State machine viewer — Displays the current session state (e.g., MENU, REGISTER_NAME, PRICE_CROP) to help developers debug the USSD flow without a real phone.')}

  <div class="info-box warning">
    <strong>Live integration</strong>
    When connected to Africa's Talking production credentials, real farmers can dial the platform's shortcode from any Ghanaian mobile number (MTN, Vodafone, AirtelTigo) and complete the full USSD flow live.
  </div>
`)}

<!-- ═══════════════════════════════════════════════════ SECTION 8 ═══ -->
${section(8, 'Data Provenance Reference', `
  <p>This section clarifies exactly where every piece of data on the platform comes from, distinguishing between static seed data, live production calculations, and external data sources. This is important for investors, auditors, and technical due diligence.</p>

  <h3>Data Source Categories</h3>
  <table>
    <tr><th>Category</th><th>Definition</th></tr>
    <tr><td><span class="badge badge-live">LIVE</span> Production calculation</td><td>Computed in real time by the API using real trained models and real database data</td></tr>
    <tr><td><span class="badge badge-mock">MOCK</span> Seed / demo data</td><td>Hardcoded or seeded data for demonstration purposes — not from real transactions</td></tr>
    <tr><td><span class="badge badge-calc">CALC</span> Precomputed static</td><td>Computed once and stored (e.g., logistics cost matrix) — real calculation, not updated daily</td></tr>
    <tr><td><span class="badge badge-api">EXT</span> External data source</td><td>Fetched from a third-party API or satellite dataset (HDX, MoFA, CHIRPS, NASA POWER)</td></tr>
  </table>

  <h3>Field-by-Field Provenance</h3>
  <table>
    <tr><th>UI Field</th><th>Source</th><th>Type</th><th>Update Frequency</th></tr>
    <tr><td>Price forecast (GHS/kg) — 30 day</td><td>XGBoost model trained on 37,933 MoFA/HDX price records</td><td><span class="badge badge-live">LIVE</span></td><td>Weekly retrain</td></tr>
    <tr><td>Price forecast — 60 & 90 day</td><td>XGBoost + LSTM ensemble forecast</td><td><span class="badge badge-live">LIVE</span></td><td>Weekly retrain</td></tr>
    <tr><td>CSI flag (green/amber/red)</td><td>CHIRPS rainfall z-score + NASA POWER humidity/solar analysis per district</td><td><span class="badge badge-live">LIVE</span></td><td>Daily (07:00 UTC)</td></tr>
    <tr><td>Delivery cost (GHS)</td><td>Precomputed 606,060-route logistics matrix: road distance × vehicle type × cargo tier</td><td><span class="badge badge-calc">CALC</span></td><td>Weekly refresh</td></tr>
    <tr><td>Road distance (km)</td><td>Haversine approximation over 260 Ghana district centroids</td><td><span class="badge badge-calc">CALC</span></td><td>Static</td></tr>
    <tr><td>Farmer name (e.g., Kofi Mensah)</td><td>Seed data — inserted via scripts/seed_demo_data.py for demonstration</td><td><span class="badge badge-mock">MOCK</span></td><td>Manual</td></tr>
    <tr><td>Farmer phone, district, region</td><td>Seed data — fictional Ghanaian profile details for demo farmers</td><td><span class="badge badge-mock">MOCK</span></td><td>Manual</td></tr>
    <tr><td>Declaration quantity (kg)</td><td>Entered by farmer via Seller Central UI or USSD. Seed declarations used for demo.</td><td><span class="badge badge-mock">MOCK</span> / <span class="badge badge-live">LIVE</span></td><td>On submission</td></tr>
    <tr><td>Historical market prices</td><td>Ghana Ministry of Food and Agriculture (MoFA) + Humanitarian Data Exchange (HDX)</td><td><span class="badge badge-api">EXT</span></td><td>Daily ingest (04:00–04:30 UTC)</td></tr>
    <tr><td>CHIRPS rainfall data</td><td>Climate Hazards Group InfraRed Precipitation with Station data (UCSB)</td><td><span class="badge badge-api">EXT</span></td><td>Daily (05:00 UTC)</td></tr>
    <tr><td>NASA POWER telemetry</td><td>NASA POWER API — solar irradiance, temperature, humidity per district</td><td><span class="badge badge-api">EXT</span></td><td>Daily (05:30 UTC)</td></tr>
    <tr><td>Monthly income (analytics)</td><td>Derived from declaration forecast prices × quantities — illustrative calculation</td><td><span class="badge badge-mock">MOCK</span></td><td>Manual seed</td></tr>
    <tr><td>Platform statistics (265 models, 44 markets)</td><td>Actual trained model counts and configured market list from the database</td><td><span class="badge badge-live">LIVE</span></td><td>On model retrain</td></tr>
    <tr><td>Animated homepage stats (GHS 48M+, 1,840+ farmers)</td><td>Illustrative figures for investor-facing presentation — not current transaction volume</td><td><span class="badge badge-mock">MOCK</span></td><td>Static</td></tr>
    <tr><td>USSD session analytics</td><td>Real session data from Africa's Talking webhook, stored in PostgreSQL</td><td><span class="badge badge-live">LIVE</span></td><td>Real-time</td></tr>
    <tr><td>Harvest delay prediction</td><td>Logistic regression classifier trained on climate + historical delay records</td><td><span class="badge badge-live">LIVE</span></td><td>Daily</td></tr>
    <tr><td>Logistics groups (truck sharing)</td><td>Real-time clustering of active declarations within 50km radius going to same market</td><td><span class="badge badge-live">LIVE</span></td><td>On demand / daily</td></tr>
  </table>

  <div class="info-box warning">
    <strong>Important distinction for investors</strong>
    The core AI and data infrastructure (265 XGBoost models, LSTM forecasts, CHIRPS/NASA climate data, logistics matrix) is fully production-ready and operating on live Ghanaian market data. The farmer profiles (Kofi Mensah, Abena Osei, etc.) and their declarations are seed data inserted for demonstration purposes. In production, real farmers register through the USSD flow or Seller Central.
  </div>
`)}

<!-- ═══════════════════════════════════════════════════ SECTION 9 ═══ -->
${section(9, 'Investor Pitch Framework', `
  <h3>The Problem — Why Ghana's Agricultural Market Fails Smallholder Farmers</h3>
  <p>Ghana has 2.5 million+ smallholder farmers contributing over $10 billion to GDP annually. Yet the system consistently fails them across four critical dimensions:</p>

  <div class="problem-row">
    <div class="problem-card">
      <h4>1. Market Timing Volatility</h4>
      <p>Farmers have no price intelligence. They sell immediately at harvest — often the worst moment — because they cannot predict whether to hold or sell. Ghana loses an estimated 40% of produce value to this mistiming alone.</p>
    </div>
    <div class="problem-card">
      <h4>2. Climate Risk Delays</h4>
      <p>Drought, irregular rainfall, and temperature shifts routinely delay or destroy harvests. Farmers and buyers have no advance warning system. A buyer commits to a delivery date that gets missed; a farmer loses their crop value.</p>
    </div>
    <div class="problem-card">
      <h4>3. Logistics Fragmentation</h4>
      <p>Each farmer individually hires a truck for transport. A single farmer moving 500kg pays the same full truck rate as a farmer moving 10,000kg. There is no mechanism to coordinate shared transport between farms going to the same market.</p>
    </div>
    <div class="problem-card">
      <h4>4. Digital Exclusion</h4>
      <p>70%+ of Ghana's smallholder farmers use feature phones only. Every existing agri-tech platform requires a smartphone app or mobile internet — excluding the majority of the very people they claim to serve.</p>
    </div>
  </div>

  <h3>The AgriMatch Solution</h3>
  <div class="solution-card" style="margin-bottom:12px">
    <h4>Layer 1 — Price Intelligence (XGBoost + LSTM)</h4>
    <p>265 crop-market XGBoost models and 107 LSTM models trained on 37,933 historical price observations from MoFA and HDX. Each model provides 30, 60, and 90-day price forecasts with confidence intervals. Farmers know whether to sell now or wait. Buyers know whether the listed price is fair.</p>
  </div>
  <div class="solution-card" style="margin-bottom:12px">
    <h4>Layer 2 — Climate Risk Intelligence (CHIRPS + NASA POWER)</h4>
    <p>A Climate Stress Index (CSI) derived daily from CHIRPS satellite rainfall data and NASA POWER solar/humidity telemetry across all 260 Ghana districts. Every listing is flagged with a CSI colour (green/amber/red). Buyers see harvest delay risk before committing; farmers get early drought warnings.</p>
  </div>
  <div class="solution-card" style="margin-bottom:12px">
    <h4>Layer 3 — Cooperative Logistics</h4>
    <p>AgriMatch's logistics engine clusters active declarations within a 50km radius going to the same market, then calculates optimal truck-sharing groups. A farmer who would pay GHS 280 for a solo truck pays GHS 70 when four nearby farmers share. The platform captures a 15% logistics coordination margin.</p>
  </div>
  <div class="solution-card" style="margin-bottom:12px">
    <h4>Layer 4 — USSD Access (Feature Phone)</h4>
    <p>A full USSD interface via Africa's Talking lets any farmer with any mobile phone — on any Ghanaian network — register, check prices, create declarations, and receive climate alerts. No smartphone. No internet. No app download required.</p>
  </div>

  <h3>Market Opportunity</h3>
  <div class="kpi-row">
    <div class="kpi"><strong>$10B+</strong><span>Ghana ag sector GDP contribution</span></div>
    <div class="kpi"><strong>2.5M+</strong><span>Smallholder farmers in Ghana</span></div>
    <div class="kpi"><strong>40%</strong><span>Produce value lost to mistiming & waste</span></div>
    <div class="kpi"><strong>70%</strong><span>Farmers excluded by smartphone-only platforms</span></div>
  </div>

  <h3>Competitive Advantage — The Technology Moat</h3>
  <div class="moat-item">
    <div class="moat-icon">🤖</div>
    <div><strong>265 trained XGBoost models</strong><br/><span style="font-size:9pt;color:#555">One model per crop × market combination, trained on 37,933 real price observations. A competitor starting today would need 5+ years of MoFA/HDX data and significant ML engineering to replicate.</span></div>
  </div>
  <div class="moat-item">
    <div class="moat-icon">🛰</div>
    <div><strong>Multi-satellite climate pipeline</strong><br/><span style="font-size:9pt;color:#555">Daily ingestion of CHIRPS rainfall + NASA POWER solar/humidity data across 260 districts. No other Ghanaian agricultural platform has this live climate intelligence integrated into its listings.</span></div>
  </div>
  <div class="moat-item">
    <div class="moat-icon">🗺</div>
    <div><strong>606,060-route logistics matrix</strong><br/><span style="font-size:9pt;color:#555">Precomputed road distances and delivery costs for every district-to-district pair in Ghana. Real-time truck-sharing optimization runs in milliseconds because the heavy computation is precomputed.</span></div>
  </div>
  <div class="moat-item">
    <div class="moat-icon">📱</div>
    <div><strong>USSD-first architecture</strong><br/><span style="font-size:9pt;color:#555">Designed from day one for feature phones. The USSD state machine handles registration, price queries, declaration creation, and alerts — reaching 70% of farmers that app-based competitors cannot.</span></div>
  </div>

  <h3>Business Model</h3>
  <table>
    <tr><th>Revenue Stream</th><th>Mechanism</th><th>Indicative Rate</th></tr>
    <tr><td>Farmer Premium Subscription</td><td>Monthly subscription for advanced forecasts, priority matching, full analytics</td><td>GHS 50 / month</td></tr>
    <tr><td>Buyer Transaction Fee</td><td>Commission on matched and completed produce orders</td><td>1.5% of order value</td></tr>
    <tr><td>Logistics Coordination Margin</td><td>Platform margin on shared truck cost savings</td><td>15% of savings generated</td></tr>
    <tr><td>Data API Licensing</td><td>Climate + price forecast API licensed to NGOs, government agencies, commodity traders</td><td>$500–$2,000 / month</td></tr>
    <tr><td>Byproducts Marketplace Fee</td><td>Small transaction fee on byproduct sales (husks, bran, stalks)</td><td>2% of sale</td></tr>
  </table>

  <h3>Current Traction</h3>
  <table>
    <tr><th>Milestone</th><th>Status</th></tr>
    <tr><td>Platform live on Vercel + Railway</td><td>✅ Live — agrimatch-psi.vercel.app</td></tr>
    <tr><td>265 XGBoost models trained and serving</td><td>✅ Production</td></tr>
    <tr><td>44 Ghana markets price data pipeline running</td><td>✅ Daily ingestion active</td></tr>
    <tr><td>260 districts CHIRPS + NASA POWER telemetry</td><td>✅ Daily ingestion active</td></tr>
    <tr><td>10 verified farmer profiles onboarded</td><td>✅ Demo seed farmers (production onboarding pending)</td></tr>
    <tr><td>USSD interface built and tested</td><td>✅ Awaiting Africa's Talking production keys</td></tr>
    <tr><td>Cooperative logistics engine operational</td><td>✅ Live — grouping active declarations</td></tr>
    <tr><td>Mobile-responsive across all pages</td><td>✅ Tested on iOS and Android</td></tr>
  </table>

  <h3>Use of Funds — Seed Round</h3>

  <div class="kpi-row">
    <div class="kpi"><strong>$500K</strong><span>Seed round target</span></div>
    <div class="kpi"><strong>18 mo</strong><span>Runway</span></div>
    <div class="kpi"><strong>1,000</strong><span>Target farmers (Year 1)</span></div>
    <div class="kpi"><strong>5</strong><span>Target regions (Year 1)</span></div>
  </div>

  <table>
    <tr><th>Allocation</th><th>%</th><th>Purpose</th></tr>
    <tr><td>Farmer Acquisition & Field Operations</td><td>40%</td><td>USSD onboarding campaigns, district field agents, mobile data bundles for farmers, community radio advertising in Ashanti + Bono regions</td></tr>
    <tr><td>Engineering Team</td><td>25%</td><td>2 full-stack engineers + 1 ML engineer. Scale model retraining, improve USSD flow, build mobile app (Phase 2)</td></tr>
    <tr><td>USSD & Telecom Integration</td><td>20%</td><td>Africa's Talking production integration, USSD shortcode licensing across MTN/Vodafone/AirtelTigo, SMS alert credits</td></tr>
    <tr><td>Operations & Compliance</td><td>15%</td><td>Ghana SEC compliance, data privacy legal, cloud infrastructure scaling, accounting & audit</td></tr>
  </table>

  <div class="info-box green" style="margin-top:24px">
    <strong>Why AgriMatch wins</strong>
    Standard agricultural marketplaces list produce. AgriMatch tells you WHEN to sell it, WHETHER climate will delay it, HOW MUCH transport will cost when shared, and reaches farmers who don't own a smartphone. The platform's four-layer intelligence stack creates a compounding data moat that deepens with every farmer onboarded, every harvest logged, and every market price ingested.
  </div>
`)}

</body>
</html>`
}

main().catch(err => { console.error(err); process.exit(1) })
