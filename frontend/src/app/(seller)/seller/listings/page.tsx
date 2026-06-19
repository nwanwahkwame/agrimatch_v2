'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { PlusCircle, Package, Pencil, Trash2, X, Loader2, AlertTriangle } from 'lucide-react'
import API from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { farmerDbId } from '@/lib/auth'
import { cropImageSrc } from '@/lib/cropImage'

const CROPS = [
  'maize', 'tomato', 'onion', 'cassava', 'rice', 'plantain',
  'groundnut', 'sorghum', 'soybean', 'pepper', 'cowpea', 'millet', 'yam', 'garden_egg',
]

function cropLabel(c: string) {
  return c.replace(/_/g, ' ').replace(/^\w/, x => x.toUpperCase())
}

function CropThumb({ crop, seed }: { crop: string; seed?: number }) {
  return (
    <Image
      src={cropImageSrc(crop, seed)}
      alt={crop}
      width={28}
      height={28}
      className="rounded object-cover shrink-0"
    />
  )
}

interface Declaration {
  id: number
  crop: string
  quantity_kg: number
  harvest_date: string
  status: string
  price_forecast_ghs: number | null
  csi_flag: string
  byproduct_count: number
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function Skel() {
  return (
    <tr>
      {[...Array(7)].map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded animate-pulse" />
        </td>
      ))}
    </tr>
  )
}

// ── Edit modal ────────────────────────────────────────────────────────────────

function EditModal({
  decl,
  onClose,
  onSaved,
}: {
  decl: Declaration
  onClose: () => void
  onSaved: () => void
}) {
  const qtyBags = Math.round(decl.quantity_kg / 100)
  const [crop,    setCrop]    = useState(decl.crop)
  const [bags,    setBags]    = useState(String(qtyBags))
  const [date,    setDate]    = useState(decl.harvest_date.slice(0, 10))
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!bags || !date) { setError('Please fill in all fields'); return }
    setLoading(true); setError('')
    try {
      await API.patch(`/api/declarations/${decl.id}`, {
        crop,
        quantity_bags: Number(bags),
        harvest_date:  date,
      })
      onSaved()
    } catch {
      setError('Failed to save changes. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-lg border border-[#DDDDDD] w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#EEEEEE]">
          <h2 className="text-base font-bold text-[#0F1111]">Edit Listing AM-{decl.id}</h2>
          <button onClick={onClose} className="text-[#565959] hover:text-[#0F1111]">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="mx-5 mt-4 rounded bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={save} className="p-5 flex flex-col gap-4">
          <div>
            <label className="block text-sm font-semibold text-[#0F1111] mb-1.5">Crop</label>
            <select
              value={crop}
              onChange={e => setCrop(e.target.value)}
              className="w-full border border-[#DDDDDD] rounded px-3 py-2.5 text-sm bg-white outline-none focus:border-[#22C55E] focus:ring-1 focus:ring-[#22C55E]"
            >
              {CROPS.map(c => (
                <option key={c} value={c}>{cropLabel(c)}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-semibold text-[#0F1111] mb-1.5">
              Quantity (bags) <span className="font-normal text-[#565959]">1 bag = 100 kg</span>
            </label>
            <input
              type="number"
              min="1"
              value={bags}
              onChange={e => setBags(e.target.value)}
              className="w-full border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E] focus:ring-1 focus:ring-[#22C55E]"
            />
            {bags && <p className="text-xs text-[#565959] mt-1">{(Number(bags) * 100).toLocaleString()} kg total</p>}
          </div>

          <div>
            <label className="block text-sm font-semibold text-[#0F1111] mb-1.5">Harvest date</label>
            <input
              type="date"
              value={date}
              onChange={e => setDate(e.target.value)}
              min={new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)}
              className="w-full border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E] focus:ring-1 focus:ring-[#22C55E]"
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-[#DDDDDD] text-[#565959] font-semibold text-sm py-2.5 rounded hover:bg-[#F7F7F7] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-[#22C55E] hover:bg-[#4ADE80] disabled:opacity-60 text-[#131921] font-bold text-sm py-2.5 rounded transition-colors flex items-center justify-center gap-2"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Delete confirmation modal ─────────────────────────────────────────────────

function DeleteModal({
  decl,
  onClose,
  onDeleted,
}: {
  decl: Declaration
  onClose: () => void
  onDeleted: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  async function confirm() {
    setLoading(true); setError('')
    try {
      await API.delete(`/api/declarations/${decl.id}`)
      onDeleted()
    } catch {
      setError('Failed to remove listing. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-lg border border-[#DDDDDD] w-full max-w-sm shadow-xl p-6 flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-6 w-6 text-red-500 shrink-0 mt-0.5" />
          <div>
            <h2 className="text-base font-bold text-[#0F1111]">Remove listing AM-{decl.id}?</h2>
            <p className="text-sm text-[#565959] mt-1">
              This will cancel your <span className="font-semibold">{cropLabel(decl.crop)}</span> listing.
              Buyers will no longer see it. This cannot be undone.
            </p>
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
        )}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 border border-[#DDDDDD] text-[#565959] font-semibold text-sm py-2.5 rounded hover:bg-[#F7F7F7] transition-colors"
          >
            Keep it
          </button>
          <button
            onClick={confirm}
            disabled={loading}
            className="flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white font-bold text-sm py-2.5 rounded transition-colors flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? 'Removing...' : 'Remove listing'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ListingsPage() {
  const { user }                = useAuth()
  const farmerId                = farmerDbId(user)
  const [decls,   setDecls]     = useState<Declaration[]>([])
  const [loading, setLoading]   = useState(true)
  const [editTarget,   setEditTarget]   = useState<Declaration | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Declaration | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    API.get(`/api/declarations/farmer/${farmerId}`)
      .then(r => setDecls(r.data as Declaration[]))
      .finally(() => setLoading(false))
  }, [farmerId])

  useEffect(() => { load() }, [load])

  return (
    <>
      {editTarget && (
        <EditModal
          decl={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => { setEditTarget(null); load() }}
        />
      )}
      {deleteTarget && (
        <DeleteModal
          decl={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={() => { setDeleteTarget(null); load() }}
        />
      )}

      <div className="p-6 flex flex-col gap-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold text-[#0F1111]">Inventory</h1>
            <p className="text-sm text-[#565959]">All your active produce listings</p>
          </div>
          <Link
            href="/seller/new"
            className="flex items-center gap-2 bg-[#22C55E] hover:bg-[#4ADE80] text-[#131921] font-bold text-sm px-4 py-2 rounded transition-colors"
          >
            <PlusCircle className="h-4 w-4" /> Add a Listing
          </Link>
        </div>

        <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#F7F7F7] border-b border-[#EEEEEE]">
                  {['Listing ID', 'Crop', 'Quantity (kg)', 'Harvest date', 'Forecast price', 'Climate', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-[#565959]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  [...Array(4)].map((_, i) => <Skel key={i} />)
                ) : decls.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-16 text-center">
                      <Package className="mx-auto h-10 w-10 text-gray-300 mb-3" />
                      <p className="text-sm text-[#565959] mb-2">No listings yet</p>
                      <Link href="/seller/new" className="text-sm text-[#007185] hover:underline font-semibold">
                        + Add your first listing
                      </Link>
                    </td>
                  </tr>
                ) : (
                  decls.map((d, i) => (
                    <tr key={d.id} className={`border-b border-[#EEEEEE] hover:bg-[#F7F7F7] ${i % 2 ? 'bg-[#FAFAFA]' : ''}`}>
                      <td className="px-4 py-3 font-mono text-[#007185] font-semibold">AM-{d.id}</td>
                      <td className="px-4 py-3 font-medium text-[#0F1111]">
                        <span className="flex items-center gap-2">
                          <CropThumb crop={d.crop} seed={d.id} />
                          {cropLabel(d.crop)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[#565959]">{d.quantity_kg.toLocaleString()}</td>
                      <td className="px-4 py-3 text-[#565959]">{fmtDate(d.harvest_date)}</td>
                      <td className="px-4 py-3 font-semibold text-[#0F1111]">
                        {d.price_forecast_ghs ? `GHS ${d.price_forecast_ghs.toFixed(2)}/kg` : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          d.csi_flag === 'normal' ? 'bg-green-100 text-green-700' :
                          d.csi_flag === 'watch'  ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {d.csi_flag}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setEditTarget(d)}
                            className="flex items-center gap-1 text-xs font-semibold text-[#007185] hover:text-[#005f73] transition-colors"
                            title="Edit listing"
                          >
                            <Pencil className="h-3.5 w-3.5" /> Edit
                          </button>
                          <span className="text-[#DDDDDD]">|</span>
                          <button
                            onClick={() => setDeleteTarget(d)}
                            className="flex items-center gap-1 text-xs font-semibold text-red-600 hover:text-red-800 transition-colors"
                            title="Remove listing"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Remove
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  )
}
