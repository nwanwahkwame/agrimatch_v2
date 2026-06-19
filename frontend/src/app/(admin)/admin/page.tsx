'use client'

import { useState, useEffect } from 'react'
import { CheckCircle, XCircle, Loader2, PhoneCall, Link as LinkIcon } from 'lucide-react'
import Link from 'next/link'
import API from '@/lib/api'

// ─── Types ─────────────────────────────────────────────────────────────────────

interface ModelsStatus {
  xgboost_models: number
  lstm_models: number
  delay_classifier: boolean
  api_version: string
  last_updated: string
}

interface UssdStats {
  total_sessions_today: number
  total_sessions_week: number
  completed_declarations_via_ussd: number
  avg_session_duration_seconds: number
  most_common_drop_off_state: string
  active_sessions_now: number
}

interface AlertEntry {
  id: number
  declaration_id: number
  phone_number: string
  alert_type: string
  message: string
  status: string
  sent_at: string
  error_detail: string | null
}

type ActionKey = 'csi' | 'alerts' | 'logistics' | 'models'
type ActionState = 'idle' | 'loading' | 'success' | 'error'

// ─── Static data ───────────────────────────────────────────────────────────────

const DB_ROWS = [
  { table: 'clean_prices',       count: '37,933',     live: false },
  { table: 'chirps_daily',       count: '1,594,845',  live: false },
  { table: 'nasa_power_daily',   count: '1,663,846',  live: false },
  { table: 'climate_indicators', count: '1,665,300',  live: false },
  { table: 'feature_store',      count: '20,718',     live: false },
  { table: 'model_baselines',    count: '60',         live: false },
  { table: 'farmers',            count: '3',          live: true  },
  { table: 'farmer_declarations',count: '4',          live: true  },
  { table: 'transport_providers',count: '3',          live: true  },
  { table: 'logistics_costs',    count: '606,060',    live: false },
]

const JOBS = [
  { name: 'chirps_daily_update',      schedule: '05:00 UTC daily'  },
  { name: 'nasa_power_daily_update',  schedule: '05:30 UTC daily'  },
  { name: 'climate_indicators_daily', schedule: '06:00 UTC daily'  },
  { name: 'run_csi_update',           schedule: '07:00 UTC daily'  },
  { name: 'update_declarations',      schedule: '07:30 UTC daily'  },
  { name: 'run_fuel_price_scrape',    schedule: 'Mon 06:30 UTC'    },
  { name: 'cooperative_logistics',    schedule: '22:00 UTC daily'  },
  { name: 'run_all_alert_checks',     schedule: '08:00 UTC daily'  },
]

const QUICK_ACTIONS: { key: ActionKey; label: string; desc: string; method: string; url: string }[] = [
  { key: 'csi',       label: 'Run CSI Update',           desc: 'Recompute harvest delay predictions', method: 'POST', url: '/api/delay/update-declarations' },
  { key: 'alerts',    label: 'Run Alert Check',          desc: 'Send pending SMS alerts',             method: 'POST', url: '/api/alerts/run'                },
  { key: 'logistics', label: 'Run Logistics Grouping',   desc: 'Group farms for truck sharing',       method: 'GET',  url: '/api/logistics/groups?save=true'  },
  { key: 'models',    label: 'Check Models',             desc: 'Verify ML model health',              method: 'GET',  url: '/api/models/status'               },
]

// ─── Helpers ───────────────────────────────────────────────────────────────────

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
  })
}

function Skel({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[#C8D8D2]/40 ${className}`} />
}

// ─── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="font-display mb-3 text-lg font-bold text-[#0F1613]">{title}</h2>
      <div className="rounded-xl border border-[#C8D8D2] bg-white shadow-sm overflow-x-auto">
        {children}
      </div>
    </section>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const [models,    setModels]    = useState<ModelsStatus | null>(null)
  const [ussd,      setUssd]      = useState<UssdStats | null>(null)
  const [alerts,    setAlerts]    = useState<AlertEntry[]>([])
  const [loading,   setLoading]   = useState(true)
  const [actionStates, setActionStates] = useState<Record<ActionKey, ActionState>>({
    csi: 'idle', alerts: 'idle', logistics: 'idle', models: 'idle',
  })
  const [actionResults, setActionResults] = useState<Record<ActionKey, string>>({
    csi: '', alerts: '', logistics: '', models: '',
  })

  useEffect(() => {
    let alive = true
    Promise.allSettled([
      API.get('/api/models/status'),
      API.get('/api/alerts/log/1?limit=5'),
      API.get('/api/admin/ussd/stats'),
    ]).then(([mRes, aRes, uRes]) => {
      if (!alive) return
      if (mRes.status === 'fulfilled') setModels(mRes.value.data as ModelsStatus)
      if (aRes.status === 'fulfilled') setAlerts((aRes.value.data.alerts ?? []).slice(0, 5) as AlertEntry[])
      if (uRes.status === 'fulfilled') setUssd(uRes.value.data as UssdStats)
    }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  async function runAction(key: ActionKey, method: string, url: string) {
    setActionStates(s => ({ ...s, [key]: 'loading' }))
    setActionResults(r => ({ ...r, [key]: '' }))
    try {
      const resp = method === 'POST'
        ? await API.post(url)
        : await API.get(url)
      const preview = JSON.stringify(resp.data).slice(0, 120)
      setActionStates(s => ({ ...s, [key]: 'success' }))
      setActionResults(r => ({ ...r, [key]: preview }))
    } catch (e: unknown) {
      setActionStates(s => ({ ...s, [key]: 'error' }))
      const msg = e instanceof Error ? e.message : 'Request failed'
      setActionResults(r => ({ ...r, [key]: msg }))
    }
  }

  const healthy = models && models.xgboost_models > 0 && models.lstm_models > 0 && models.delay_classifier

  return (
    <div className="min-h-screen bg-[#F7FAF8]">

      {/* Header */}
      <section
        className="px-6 py-6"
        style={{
          background: '#145228',
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
        }}
      >
        <div className="mx-auto max-w-screen-xl flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold text-white">AgriMatch Admin</h1>
            <p className="mt-1 text-sm text-[#7DCFA0]">Platform health and data pipeline status</p>
          </div>
          {models && (
            <div className="text-right">
              <div className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${healthy ? 'bg-[#E8F5EE] text-[#1D6B3A]' : 'bg-red-100 text-red-700'}`}>
                {healthy ? <CheckCircle className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                {healthy ? 'All systems healthy' : 'Issues detected'}
              </div>
              <p className="mt-1 text-xs text-[#7DCFA0]">
                Updated {fmtDateTime(models.last_updated)}
              </p>
            </div>
          )}
        </div>
      </section>

      <div className="mx-auto max-w-screen-xl space-y-8 px-6 py-8">

        {/* ── Section 1: Model status ───────────────────────────── */}
        <section>
          <h2 className="font-display mb-3 text-lg font-bold text-[#0F1613]">Model Status</h2>
          {loading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[0,1,2,3].map(i => <Skel key={i} className="h-20" />)}
            </div>
          ) : models ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { label: 'XGBoost models',    value: `${models.xgboost_models} loaded`,  ok: models.xgboost_models > 0 },
                { label: 'LSTM models',        value: `${models.lstm_models} loaded`,     ok: models.lstm_models > 0    },
                { label: 'Delay classifier',   value: models.delay_classifier ? 'Active' : 'Inactive', ok: models.delay_classifier },
                { label: 'API version',        value: models.api_version,                 ok: true                      },
              ].map(({ label, value, ok }) => (
                <div
                  key={label}
                  className={`rounded-xl border p-4 ${ok ? 'border-[#4DB876]/40 bg-[#F4FAF6]' : 'border-red-200 bg-red-50'}`}
                >
                  <p className="text-xs text-[#7A9088]">{label}</p>
                  <p className={`mt-1 font-display text-lg font-bold ${ok ? 'text-[#1D6B3A]' : 'text-red-600'}`}>
                    {value}
                  </p>
                  <div className={`mt-1 flex items-center gap-1 text-xs ${ok ? 'text-[#2EA05A]' : 'text-red-500'}`}>
                    {ok ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                    {ok ? 'Healthy' : 'Failed'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[#7A9088]">Model status unavailable</p>
          )}
        </section>

        {/* ── Section 2: USSD analytics ────────────────────────── */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-lg font-bold text-[#0F1613]">USSD Analytics (*384#)</h2>
            <Link
              href="/admin/ussd-test"
              className="flex items-center gap-1.5 rounded-lg border border-[#1D6B3A] px-3 py-1.5 text-xs font-medium text-[#1D6B3A] hover:bg-[#E8F5EE] transition-colors"
            >
              <PhoneCall className="h-3.5 w-3.5" />
              Open simulator
            </Link>
          </div>
          {loading ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {[0,1,2,3,4,5].map(i => <div key={i} className="animate-pulse rounded-xl bg-[#C8D8D2]/40 h-20" />)}
            </div>
          ) : ussd ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {[
                { label: 'Sessions today',       value: ussd.total_sessions_today.toString(),              accent: false },
                { label: 'Sessions (7 days)',     value: ussd.total_sessions_week.toString(),               accent: false },
                { label: 'Declarations via USSD', value: ussd.completed_declarations_via_ussd.toString(),  accent: true  },
                { label: 'Avg session (s)',        value: ussd.avg_session_duration_seconds != null ? ussd.avg_session_duration_seconds.toFixed(1) : '--', accent: false },
                { label: 'Common drop-off',        value: ussd.most_common_drop_off_state,                  accent: false },
                { label: 'Active now',             value: ussd.active_sessions_now.toString(),              accent: ussd.active_sessions_now > 0 },
              ].map(({ label, value, accent }) => (
                <div
                  key={label}
                  className={`rounded-xl border p-4 ${accent ? 'border-[#4DB876]/40 bg-[#F4FAF6]' : 'border-[#C8D8D2] bg-white'}`}
                >
                  <p className="text-xs text-[#7A9088]">{label}</p>
                  <p className={`mt-1 font-display text-lg font-bold truncate ${accent ? 'text-[#1D6B3A]' : 'text-[#0F1613]'}`}>
                    {value}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-xl border border-[#C8D8D2] bg-white p-4 shadow-sm">
              <LinkIcon className="h-4 w-4 text-[#C8D8D2]" />
              <p className="text-sm text-[#7A9088]">USSD stats unavailable</p>
            </div>
          )}
        </section>

        {/* ── Section 3: Database summary ───────────────────────── */}
        <Section title="Database Summary">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#EEF4F1] bg-[#F7FAF8]">
                <th className="px-5 py-3 text-left text-xs font-medium text-[#7A9088]">Table</th>
                <th className="px-5 py-3 text-right text-xs font-medium text-[#7A9088]">Row count</th>
                <th className="px-5 py-3 text-right text-xs font-medium text-[#7A9088]">Type</th>
              </tr>
            </thead>
            <tbody>
              {DB_ROWS.map(({ table, count, live }, i) => (
                <tr
                  key={table}
                  className={`border-b border-[#EEF4F1] ${i % 2 === 0 ? '' : 'bg-[#F7FAF8]/50'}`}
                >
                  <td className="px-5 py-2.5 font-mono text-sm text-[#2D3F38]">{table}</td>
                  <td className="px-5 py-2.5 text-right font-semibold text-[#1D6B3A]">{count}</td>
                  <td className="px-5 py-2.5 text-right">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${live ? 'bg-[#E8F5EE] text-[#1D6B3A]' : 'bg-[#EEF4F1] text-[#445E54]'}`}>
                      {live ? 'live' : 'static'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        {/* ── Section 4: Scheduler status ──────────────────────── */}
        <Section title="Scheduler Status">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#EEF4F1] bg-[#F7FAF8]">
                <th className="px-5 py-3 text-left text-xs font-medium text-[#7A9088]">Job</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-[#7A9088]">Schedule</th>
                <th className="px-5 py-3 text-right text-xs font-medium text-[#7A9088]">Status</th>
              </tr>
            </thead>
            <tbody>
              {JOBS.map(({ name, schedule }, i) => (
                <tr
                  key={name}
                  className={`border-b border-[#EEF4F1] ${i % 2 === 0 ? '' : 'bg-[#F7FAF8]/50'}`}
                >
                  <td className="px-5 py-2.5 font-mono text-sm text-[#2D3F38]">{name}</td>
                  <td className="px-5 py-2.5 text-sm text-[#445E54]">{schedule}</td>
                  <td className="px-5 py-2.5 text-right">
                    <span className="flex items-center justify-end gap-1 text-xs text-[#2EA05A]">
                      <CheckCircle className="h-3.5 w-3.5" /> Active
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        {/* ── Section 5: Recent alerts ──────────────────────────── */}
        <Section title="Recent Alerts — Farmer Kofi (ID 1)">
          {loading ? (
            <div className="flex flex-col gap-2 p-4">
              {[0,1,2].map(i => <Skel key={i} className="h-8" />)}
            </div>
          ) : alerts.length === 0 ? (
            <p className="px-5 py-6 text-sm text-[#7A9088]">No alerts logged yet</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#EEF4F1] bg-[#F7FAF8]">
                  {['Type', 'Message preview', 'Sent at', 'Status'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-[#7A9088]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {alerts.map((a, i) => (
                  <tr key={a.id} className={`border-b border-[#EEF4F1] ${i % 2 === 0 ? '' : 'bg-[#F7FAF8]/50'}`}>
                    <td className="px-4 py-2.5">
                      <span className="rounded-full bg-[#EEF4F1] px-2 py-0.5 text-xs capitalize text-[#445E54]">
                        {a.alert_type}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 max-w-xs truncate text-xs text-[#445E54]" title={a.message}>
                      {a.message.slice(0, 70)}{a.message.length > 70 ? '…' : ''}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-[#7A9088] whitespace-nowrap">
                      {new Date(a.sent_at).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        a.status === 'sent'    ? 'bg-[#E8F5EE] text-[#1D6B3A]' :
                        a.status === 'skipped' ? 'bg-[#EEF4F1] text-[#445E54]' :
                        'bg-red-50 text-red-600'
                      }`}>
                        {a.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>

        {/* ── Section 6: Quick actions ──────────────────────────── */}
        <section>
          <h2 className="font-display mb-3 text-lg font-bold text-[#0F1613]">Quick Actions</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {QUICK_ACTIONS.map(({ key, label, desc, method, url }) => {
              const state = actionStates[key]
              const result = actionResults[key]
              return (
                <div key={key} className="flex flex-col rounded-xl border border-[#C8D8D2] bg-white p-4 shadow-sm">
                  <p className="mb-1 text-sm font-semibold text-[#0F1613]">{label}</p>
                  <p className="mb-4 text-xs text-[#7A9088]">{desc}</p>

                  {result && (
                    <div
                      className={`mb-3 rounded-lg px-2.5 py-2 text-xs break-all ${
                        state === 'success' ? 'bg-[#E8F5EE] text-[#1D6B3A]' : 'bg-red-50 text-red-600'
                      }`}
                    >
                      {result}
                    </div>
                  )}

                  <button
                    onClick={() => runAction(key, method, url)}
                    disabled={state === 'loading'}
                    className={`mt-auto flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-colors ${
                      state === 'loading'
                        ? 'bg-[#EEF4F1] text-[#7A9088] cursor-wait'
                        : state === 'success'
                          ? 'bg-[#E8F5EE] text-[#1D6B3A] border border-[#4DB876]/40'
                          : state === 'error'
                            ? 'bg-red-50 text-red-600 border border-red-200'
                            : 'bg-[#1D6B3A] text-white hover:bg-[#145228]'
                    }`}
                  >
                    {state === 'loading' && <Loader2 className="h-4 w-4 animate-spin" />}
                    {state === 'success' && <CheckCircle className="h-4 w-4" />}
                    {state === 'error'   && <XCircle className="h-4 w-4" />}
                    {state === 'idle'    ? label : state === 'loading' ? 'Running…' : state === 'success' ? 'Done' : 'Failed'}
                  </button>
                </div>
              )
            })}
          </div>
        </section>

      </div>
    </div>
  )
}
