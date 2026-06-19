'use client'

import { useState } from 'react'
import Link from 'next/link'
import { CheckCircle, ArrowLeft, Loader2 } from 'lucide-react'
import API from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { farmerDbId } from '@/lib/auth'

const CROPS = ['maize', 'tomato', 'onion', 'cassava', 'rice', 'plantain']

export default function NewListingPage() {
  const { user }              = useAuth()
  const farmerId              = farmerDbId(user)
  const districtId            = user?.districtId ?? 32
  const [crop,      setCrop]      = useState('maize')
  const [bags,      setBags]      = useState('')
  const [date,      setDate]      = useState('')
  const [loading,   setLoading]   = useState(false)
  const [success,   setSuccess]   = useState<{ id: number; sms: string } | null>(null)
  const [error,     setError]     = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!bags || !date) { setError('Please fill in all fields'); return }
    setLoading(true); setError('')
    try {
      const r = await API.post('/api/declarations', {
        farmer_id:     farmerId,
        crop,
        quantity_bags: Number(bags),
        district_id:   districtId,
        harvest_date:  date,
        source:        'web',
        byproducts:    [],
      })
      setSuccess({ id: r.data.declaration_id, sms: r.data.confirmation_sms })
      setCrop('maize'); setBags(''); setDate('')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Submission failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-xl">
      <Link href="/seller" className="flex items-center gap-1.5 text-sm text-[#007185] hover:underline mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to Dashboard
      </Link>

      <h1 className="text-xl font-bold text-[#0F1111] mb-1">Add a Listing</h1>
      <p className="text-sm text-[#565959] mb-6">List your produce to be matched with buyers across Ghana</p>

      {success && (
        <div className="mb-6 rounded-lg bg-[#DFF0D8] border border-[#3C763D] p-4">
          <div className="flex items-center gap-2 text-green-700 font-bold mb-1">
            <CheckCircle className="h-5 w-5" /> Listed successfully! Ref: AM-{success.id}
          </div>
          <p className="text-sm text-green-700">{success.sms}</p>
          <Link href="/seller/listings" className="mt-2 inline-block text-sm text-[#007185] hover:underline">
            View all listings &rarr;
          </Link>
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={submit} className="bg-white rounded-lg border border-[#DDDDDD] p-6 flex flex-col gap-5">

        <div>
          <label className="block text-sm font-semibold text-[#0F1111] mb-1.5">Crop *</label>
          <select
            value={crop}
            onChange={e => setCrop(e.target.value)}
            className="w-full border border-[#DDDDDD] rounded px-3 py-2.5 text-sm bg-white outline-none focus:border-[#22C55E] focus:ring-1 focus:ring-[#22C55E]"
          >
            {CROPS.map(c => (
              <option key={c} value={c}>{c.replace(/_/g, ' ').replace(/^\w/, x => x.toUpperCase())}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-semibold text-[#0F1111] mb-1.5">
            Quantity (bags) * <span className="font-normal text-[#565959]">1 bag = 100 kg</span>
          </label>
          <input
            type="number"
            min="1"
            value={bags}
            onChange={e => setBags(e.target.value)}
            placeholder="e.g. 50"
            className="w-full border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E] focus:ring-1 focus:ring-[#22C55E]"
          />
          {bags && <p className="text-xs text-[#565959] mt-1">{(Number(bags) * 100).toLocaleString()} kg total</p>}
        </div>

        <div>
          <label className="block text-sm font-semibold text-[#0F1111] mb-1.5">Harvest date *</label>
          <input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            min={new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)}
            className="w-full border border-[#DDDDDD] rounded px-3 py-2.5 text-sm outline-none focus:border-[#22C55E] focus:ring-1 focus:ring-[#22C55E]"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-[#22C55E] hover:bg-[#4ADE80] disabled:opacity-60 text-[#131921] font-bold py-3 rounded text-sm transition-colors flex items-center justify-center gap-2"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {loading ? 'Submitting...' : 'List Produce'}
        </button>
      </form>
    </div>
  )
}
