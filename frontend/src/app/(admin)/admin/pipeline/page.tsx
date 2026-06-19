'use client'

import { useEffect, useState } from 'react'
import { Activity, Database, CheckCircle, AlertTriangle, RefreshCw, Clock } from 'lucide-react'
import { getPipelineStats } from '@/lib/api'

interface RowCount { table: string; count: number }
interface RecentRun { source: string; run_at: string | null; rows_clean: number; rows_quarantined: number; status: string }

// Scheduler jobs are defined in code (not stored in DB) — schedule strings stay static
const SCHEDULER_JOBS = [
  { id: 'delay_declaration_update',    schedule: '07:30 UTC daily'       },
  { id: 'cooperative_logistics_daily', schedule: '22:00 UTC daily'       },
  { id: 'alerts_daily',               schedule: '08:00 UTC daily'       },
]

const TABLE_ORDER = [
  'clean_prices', 'raw_prices', 'quarantine', 'chirps', 'nasa_power',
  'climate_indicators', 'logistics_costs', 'feature_store', 'price_forecasts',
  'farmers', 'declarations', 'markets', 'districts',
]

function fmt(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function Skel() {
  return <div className="h-10 bg-gray-200 rounded animate-pulse" />
}

export default function AdminPipelinePage() {
  const [rows,    setRows]    = useState<RowCount[]>([])
  const [runs,    setRuns]    = useState<RecentRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  function load() {
    setLoading(true); setError('')
    getPipelineStats()
      .then(r => {
        const data = r.data as { row_counts: Record<string, number>; recent_runs: RecentRun[] }
        const ordered = TABLE_ORDER
          .filter(k => k in data.row_counts)
          .map(k => ({ table: k, count: data.row_counts[k] }))
        // add any extra tables not in our order list
        Object.entries(data.row_counts).forEach(([k, v]) => {
          if (!TABLE_ORDER.includes(k)) ordered.push({ table: k, count: v })
        })
        setRows(ordered)
        setRuns(data.recent_runs ?? [])
      })
      .catch(() => setError('Could not load pipeline stats from the database.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const totalRows = rows.reduce((s, r) => s + r.count, 0)
  const lastRunBySource = Object.fromEntries(runs.map(r => [r.source, r]))

  return (
    <div className="p-6 max-w-screen-xl mx-auto">

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#0F1111] mb-1">Data Pipeline</h1>
          <p className="text-sm text-[#565959]">Live row counts and ingestion history — from database</p>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-2 border border-[#DDDDDD] bg-white hover:bg-[#F0FDF4] text-sm px-3 py-2 rounded transition-colors disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 border border-red-200 bg-red-50 rounded px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Total DB rows',      value: loading ? '…' : totalRows.toLocaleString(),  icon: Database,       color: '#1D6B3A' },
          { label: 'Tables tracked',     value: loading ? '…' : rows.length,                 icon: CheckCircle,    color: '#16A34A' },
          { label: 'Scheduled jobs',     value: SCHEDULER_JOBS.length,                        icon: Activity,       color: '#2563EB' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-lg border border-[#DDDDDD] p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}18` }}>
              <Icon className="h-5 w-5" style={{ color }} />
            </div>
            <div>
              <p className="text-2xl font-bold text-[#0F1111]">{value}</p>
              <p className="text-xs text-[#565959]">{label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">

        {/* Scheduler jobs */}
        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-4 py-3 border-b border-[#EEEEEE] flex items-center gap-2">
            <Activity className="h-4 w-4 text-[#1D6B3A]" />
            <h2 className="font-semibold text-sm text-[#0F1111]">Scheduler Jobs</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F7F7F7] text-xs text-[#565959] uppercase tracking-wide">
                <tr>
                  {['Job ID', 'Schedule'].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left font-semibold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EEEEEE]">
                {SCHEDULER_JOBS.map(j => (
                  <tr key={j.id} className="hover:bg-[#FAFAFA]">
                    <td className="px-4 py-2.5 font-mono text-xs text-[#0F1111]">{j.id}</td>
                    <td className="px-4 py-2.5 text-[#565959] text-xs">{j.schedule}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* DB row counts — live from database */}
        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-4 py-3 border-b border-[#EEEEEE] flex items-center gap-2">
            <Database className="h-4 w-4 text-[#1D6B3A]" />
            <h2 className="font-semibold text-sm text-[#0F1111]">Database Row Counts</h2>
            <span className="ml-auto text-[10px] text-[#22C55E] font-semibold uppercase tracking-wide">Live</span>
          </div>
          <div className="overflow-x-auto">
            {loading ? (
              <div className="p-4 flex flex-col gap-2">
                {[...Array(6)].map((_, i) => <Skel key={i} />)}
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-[#F7F7F7] text-xs text-[#565959] uppercase tracking-wide">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-semibold">Table</th>
                    <th className="px-4 py-2.5 text-right font-semibold">Row count</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EEEEEE]">
                  {rows.map(r => (
                    <tr key={r.table} className="hover:bg-[#FAFAFA]">
                      <td className="px-4 py-2.5 font-mono text-xs text-[#0F1111]">{r.table}</td>
                      <td className="px-4 py-2.5 text-right font-semibold text-[#1D6B3A]">
                        {r.count.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Recent ingestion runs from ingestion_log */}
      {runs.length > 0 && (
        <div className="mt-6 bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-4 py-3 border-b border-[#EEEEEE] flex items-center gap-2">
            <Clock className="h-4 w-4 text-[#1D6B3A]" />
            <h2 className="font-semibold text-sm text-[#0F1111]">Recent Ingestion Runs</h2>
            <span className="ml-auto text-[10px] text-[#22C55E] font-semibold uppercase tracking-wide">Live from ingestion_log</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F7F7F7] text-xs text-[#565959] uppercase tracking-wide">
                <tr>
                  {['Source', 'Run at', 'Clean rows', 'Quarantined', 'Status'].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left font-semibold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EEEEEE]">
                {runs.map((r, i) => (
                  <tr key={i} className="hover:bg-[#FAFAFA]">
                    <td className="px-4 py-2.5 font-mono text-xs text-[#0F1111]">{r.source}</td>
                    <td className="px-4 py-2.5 text-[#565959] text-xs whitespace-nowrap">{fmt(r.run_at)}</td>
                    <td className="px-4 py-2.5 text-center font-semibold text-[#22C55E]">{r.rows_clean?.toLocaleString() ?? '—'}</td>
                    <td className="px-4 py-2.5 text-center text-[#D97706]">{r.rows_quarantined?.toLocaleString() ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        r.status === 'ok' || r.status === 'success'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-700'
                      }`}>
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
