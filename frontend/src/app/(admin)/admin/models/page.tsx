'use client'

import { useEffect, useState } from 'react'
import { Brain, BarChart2, Cpu, CheckCircle, Loader2, AlertTriangle, RefreshCw } from 'lucide-react'
import { getModelsStatus, getModelAccuracy, getAdminCrops } from '@/lib/api'

interface ModelsStatus {
  xgboost_models:   number
  lstm_models:      number
  delay_classifier: boolean
  api_version:      string
  last_updated:     string
}

interface MarketAccuracy {
  market:        string
  xgb?:         number
  lstm?:        number
  training_rows?: number
}

interface Crop { name: string; is_byproduct_source: boolean }

export default function AdminModelsPage() {
  const [status,   setStatus]   = useState<ModelsStatus | null>(null)
  const [accuracy, setAccuracy] = useState<MarketAccuracy[]>([])
  const [crops,    setCrops]    = useState<string[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(false)

  function load() {
    setLoading(true); setError(false)
    Promise.allSettled([
      getModelsStatus().then(r => setStatus(r.data)),
      getModelAccuracy().then(r => setAccuracy((r.data as MarketAccuracy[]).filter(m => m && m.market))),
      getAdminCrops().then(r => {
        const names = (r.data as Crop[]).filter(c => c && c.name && !c.is_byproduct_source).map(c => c.name)
        setCrops(names)
      }),
    ])
      .then(results => {
        if (results.every(r => r.status === 'rejected')) setError(true)
      })
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  // Per-crop model count from accuracy data
  const cropModelCount = (crop: string) =>
    accuracy.filter(m => m.xgb !== undefined).length

  const totalMarkets = status?.xgboost_models
    ? Math.round(status.xgboost_models / Math.max(crops.length, 1))
    : accuracy.length

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#0F1111] mb-1">AI Models</h1>
          <p className="text-sm text-[#565959]">XGBoost and LSTM model status and accuracy — live from model_baselines</p>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-2 border border-[#DDDDDD] bg-white hover:bg-[#F0FDF4] text-sm px-3 py-2 rounded transition-colors disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Live status cards from /api/models/status */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
        {loading ? (
          <div className="col-span-4 flex items-center gap-2 text-sm text-[#565959] py-4">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading model status...
          </div>
        ) : error ? (
          <div className="col-span-4 flex items-center gap-2 text-sm text-red-600 py-4">
            <AlertTriangle className="h-4 w-4" /> Could not reach API
          </div>
        ) : status && (
          <>
            {[
              { label: 'XGBoost models',   value: status.xgboost_models, icon: BarChart2,   color: '#22C55E' },
              { label: 'LSTM models',      value: status.lstm_models,    icon: Brain,        color: '#7C3AED' },
              { label: 'Delay classifier', value: status.delay_classifier ? 'Active' : 'Inactive', icon: Cpu, color: '#1D6B3A' },
              { label: 'API version',      value: status.api_version,    icon: CheckCircle,  color: '#2563EB' },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} className="bg-white rounded-lg border border-[#DDDDDD] p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg shrink-0 flex items-center justify-center" style={{ backgroundColor: `${color}18` }}>
                  <Icon className="h-5 w-5" style={{ color }} />
                </div>
                <div>
                  <p className="text-xl font-bold text-[#0F1111]">{value}</p>
                  <p className="text-xs text-[#565959]">{label}</p>
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">

        {/* Crop coverage — from crop_reference + model counts */}
        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-4 py-3 border-b border-[#EEEEEE]">
            <h2 className="font-semibold text-sm text-[#0F1111]">Crop coverage</h2>
            <p className="text-xs text-[#565959]">Models trained per crop (from crop_reference table)</p>
          </div>
          <div className="p-4 flex flex-col gap-3">
            {crops.length === 0 ? (
              [...Array(4)].map((_, i) => (
                <div key={i} className="h-6 bg-gray-200 rounded animate-pulse" />
              ))
            ) : crops.map(crop => {
              const count = accuracy.filter(m => m.xgb !== undefined).length
              const total = Math.max(count, totalMarkets, 1)
              return (
                <div key={crop} className="flex items-center gap-3">
                  <span className="text-xs font-medium text-[#0F1111] w-20 capitalize">{crop}</span>
                  <div className="flex-1 bg-[#EEEEEE] rounded-full h-2">
                    <div className="bg-[#1D6B3A] h-2 rounded-full" style={{ width: `${Math.min(100, (count / total) * 100)}%` }} />
                  </div>
                  <span className="text-xs text-[#565959] w-24 text-right">{count} / {total} markets</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Accuracy by market — live from model_baselines */}
        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="px-4 py-3 border-b border-[#EEEEEE] flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-sm text-[#0F1111]">Accuracy by market</h2>
              <p className="text-xs text-[#565959]">30-day accuracy from model_baselines table</p>
            </div>
            <span className="text-[10px] text-[#22C55E] font-semibold uppercase tracking-wide">Live</span>
          </div>
          <div className="overflow-x-auto">
            {loading ? (
              <div className="p-4 flex flex-col gap-2">
                {[...Array(5)].map((_, i) => <div key={i} className="h-8 bg-gray-200 rounded animate-pulse" />)}
              </div>
            ) : accuracy.length === 0 ? (
              <p className="text-sm text-[#565959] p-6 text-center">No model baseline data available yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-[#F7F7F7] text-xs text-[#565959] uppercase tracking-wide">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-semibold">Market</th>
                    <th className="px-4 py-2.5 text-right font-semibold">XGBoost</th>
                    <th className="px-4 py-2.5 text-right font-semibold">LSTM</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EEEEEE]">
                  {accuracy.filter(m => m && m.market).map(m => (
                    <tr key={m.market} className="hover:bg-[#FAFAFA]">
                      <td className="px-4 py-2.5 text-[#0F1111]">{m.market}</td>
                      <td className="px-4 py-2.5 text-right font-semibold text-[#22C55E]">
                        {m.xgb != null ? `${m.xgb}%` : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right font-semibold text-[#7C3AED]">
                        {m.lstm != null ? `${m.lstm}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Retraining schedule — schedule strings are code-defined, not DB */}
      <div className="mt-6 bg-white rounded-lg border border-[#DDDDDD] p-4">
        <h2 className="font-semibold text-sm text-[#0F1111] mb-3">Retraining schedule</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          {[
            { model: 'XGBoost (all crops)', freq: 'Weekly — every Sunday 02:00 UTC' },
            { model: 'LSTM (all crops)',    freq: 'Monthly — 1st of month 03:00 UTC' },
            { model: 'Delay classifier',   freq: 'Monthly — 1st of month 04:00 UTC' },
          ].map(r => (
            <div key={r.model} className="rounded-lg bg-[#F7FAF8] border border-[#C8D8D2] p-3">
              <p className="font-semibold text-[#0F1111] text-xs mb-1">{r.model}</p>
              <p className="text-xs text-[#565959]">{r.freq}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
