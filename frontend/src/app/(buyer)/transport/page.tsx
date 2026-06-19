'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Truck, CheckCircle, AlertCircle, Leaf } from 'lucide-react'
import API, { getAdminDistricts } from '@/lib/api'

const VEHICLE_TYPES = [
  { value: 'pickup',       label: 'Pickup Truck',   capacity: '500 – 1,500 kg'  },
  { value: 'mini_van',     label: 'Mini Van',        capacity: '800 – 2,000 kg'  },
  { value: 'medium_truck', label: 'Medium Truck',    capacity: '2,000 – 8,000 kg'},
  { value: 'large_truck',  label: 'Large Truck',     capacity: '8,000 – 30,000 kg'},
]

const REGIONS = [
  'Greater Accra','Ashanti','Eastern','Western','Central','Volta','Oti',
  'Northern','North East','Savannah','Upper East','Upper West','Bono','Bono East','Ahafo','Western North',
]

interface District { id: number; name: string; region: string }

export default function TransportRegisterPage() {
  const [districts, setDistricts] = useState<District[]>([])
  const [form, setForm] = useState({
    full_name: '',
    phone_number: '',
    business_name: '',
    district_id: '',
    vehicle_type: 'pickup',
    truck_capacity_kg: '',
    truck_count: '1',
    base_rate_per_km: '',
    service_regions: [] as string[],
  })
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [error, setError]   = useState('')
  const [result, setResult] = useState<{ provider_id: number; message: string } | null>(null)

  useEffect(() => {
    getAdminDistricts()
      .then(r => setDistricts((r.data as { id: number; district_name: string; region_name: string }[])
        .map(d => ({ id: d.id, name: d.district_name, region: d.region_name }))))
      .catch(() => {})
  }, [])

  function set(key: string, value: string) {
    setForm(f => ({ ...f, [key]: value }))
  }

  function toggleRegion(region: string) {
    setForm(f => ({
      ...f,
      service_regions: f.service_regions.includes(region)
        ? f.service_regions.filter(r => r !== region)
        : [...f.service_regions, region],
    }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (!form.district_id)        { setError('Select your base district.'); return }
    if (!form.truck_capacity_kg)  { setError('Enter truck capacity.'); return }
    if (form.service_regions.length === 0) { setError('Select at least one service region.'); return }

    setStatus('loading')
    try {
      const res = await API.post('/api/transport/register', {
        full_name:         form.full_name.trim(),
        phone_number:      form.phone_number.trim(),
        business_name:     form.business_name.trim() || undefined,
        district_id:       parseInt(form.district_id),
        vehicle_type:      form.vehicle_type,
        truck_capacity_kg: parseFloat(form.truck_capacity_kg),
        truck_count:       parseInt(form.truck_count) || 1,
        base_rate_per_km:  form.base_rate_per_km ? parseFloat(form.base_rate_per_km) : undefined,
        service_regions:   form.service_regions,
      })
      setResult(res.data)
      setStatus('success')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Registration failed. Please check your details and try again.')
      setStatus('error')
    }
  }

  if (status === 'success' && result) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center px-4 py-12 text-center">
        <CheckCircle className="h-16 w-16 text-[#22C55E] mb-4" />
        <h1 className="text-2xl font-bold text-[#0F1111] mb-2">Registration Successful!</h1>
        <p className="text-sm text-[#565959] mb-1">Provider ID: <strong className="font-mono text-[#0F1111]">{result.provider_id}</strong></p>
        <p className="text-sm text-[#565959] max-w-sm mb-6">{result.message}</p>
        <Link href="/shop" className="bg-[#22C55E] hover:bg-[#16A34A] text-white font-bold px-8 py-2.5 rounded-full text-sm transition-colors">
          Browse Marketplace
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">

      <div className="flex items-center gap-2 mb-6">
        <Leaf className="h-6 w-6 text-[#22C55E]" />
        <Link href="/" className="font-bold text-xl text-[#0F1111]">
          agri<span className="text-[#22C55E]">match</span>
        </Link>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <div className="h-10 w-10 rounded-full bg-[#22C55E]/10 flex items-center justify-center">
          <Truck className="h-5 w-5 text-[#22C55E]" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-[#0F1111]">Register as a Transport Provider</h1>
          <p className="text-sm text-[#565959]">Join the AgriMatch logistics network and earn by moving farm produce</p>
        </div>
      </div>

      {(status === 'error') && error && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded px-3 py-2.5 mb-5 text-xs text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" /> {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-[#DDDDDD] divide-y divide-[#EEEEEE]">

        {/* Personal info */}
        <div className="p-5 flex flex-col gap-4">
          <h2 className="font-bold text-sm text-[#0F1111]">Personal Information</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-[#0F1111]">Full name *</label>
              <input required value={form.full_name} onChange={e => set('full_name', e.target.value)}
                placeholder="Your full name"
                className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E]" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-[#0F1111]">Phone number *</label>
              <div className="flex gap-1">
                <span className="flex items-center border border-[#888] rounded px-2 text-sm text-[#565959] bg-[#F3F3F3]">+233</span>
                <input required value={form.phone_number} onChange={e => set('phone_number', e.target.value)}
                  placeholder="24 000 0000" type="tel"
                  className="flex-1 border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E]" />
              </div>
            </div>
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label className="text-xs font-semibold text-[#0F1111]">Business name <span className="font-normal text-[#565959]">(optional)</span></label>
              <input value={form.business_name} onChange={e => set('business_name', e.target.value)}
                placeholder="e.g. Kofi Transport Services"
                className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E]" />
            </div>
          </div>
        </div>

        {/* Vehicle info */}
        <div className="p-5 flex flex-col gap-4">
          <h2 className="font-bold text-sm text-[#0F1111]">Vehicle Information</h2>
          <div className="grid sm:grid-cols-2 gap-3">
            {VEHICLE_TYPES.map(v => (
              <label key={v.value}
                className={`flex items-center gap-3 border-2 rounded-lg p-3 cursor-pointer transition-colors ${
                  form.vehicle_type === v.value ? 'border-[#22C55E] bg-[#F0FDF4]' : 'border-[#DDDDDD] hover:border-[#22C55E]/50'
                }`}
              >
                <input type="radio" name="vehicle_type" value={v.value}
                  checked={form.vehicle_type === v.value} onChange={e => set('vehicle_type', e.target.value)}
                  className="accent-[#22C55E]" />
                <div>
                  <p className="text-sm font-semibold text-[#0F1111]">{v.label}</p>
                  <p className="text-xs text-[#565959]">{v.capacity}</p>
                </div>
              </label>
            ))}
          </div>
          <div className="grid sm:grid-cols-3 gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-[#0F1111]">Capacity (kg) *</label>
              <input required type="number" min="100" value={form.truck_capacity_kg} onChange={e => set('truck_capacity_kg', e.target.value)}
                placeholder="e.g. 2000"
                className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E]" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-[#0F1111]">No. of trucks</label>
              <input type="number" min="1" max="50" value={form.truck_count} onChange={e => set('truck_count', e.target.value)}
                className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E]" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-[#0F1111]">Rate / km (GHS) <span className="font-normal text-[#565959]">optional</span></label>
              <input type="number" min="0" step="0.01" value={form.base_rate_per_km} onChange={e => set('base_rate_per_km', e.target.value)}
                placeholder="e.g. 3.50"
                className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E]" />
            </div>
          </div>
        </div>

        {/* Location */}
        <div className="p-5 flex flex-col gap-4">
          <h2 className="font-bold text-sm text-[#0F1111]">Location &amp; Coverage</h2>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-[#0F1111]">Base district *</label>
            <select required value={form.district_id} onChange={e => set('district_id', e.target.value)}
              className="border border-[#888] rounded px-3 py-2 text-sm outline-none focus:border-[#22C55E] bg-white">
              <option value="">Select district...</option>
              {districts.map(d => <option key={d.id} value={d.id}>{d.name} ({d.region})</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-[#0F1111] block mb-2">Service regions * <span className="font-normal text-[#565959]">(select all you cover)</span></label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {REGIONS.map(r => (
                <label key={r} className={`flex items-center gap-2 border rounded px-2.5 py-1.5 cursor-pointer text-xs transition-colors ${
                  form.service_regions.includes(r) ? 'border-[#22C55E] bg-[#F0FDF4] text-[#15803D] font-semibold' : 'border-[#DDDDDD] text-[#0F1111] hover:border-[#22C55E]/50'
                }`}>
                  <input type="checkbox" checked={form.service_regions.includes(r)} onChange={() => toggleRegion(r)} className="accent-[#22C55E]" />
                  {r}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="p-5">
          <button type="submit" disabled={status === 'loading'}
            className="w-full bg-[#22C55E] hover:bg-[#16A34A] disabled:opacity-50 text-white font-bold rounded-full py-3 text-sm transition-colors flex items-center justify-center gap-2">
            <Truck className="h-4 w-4" />
            {status === 'loading' ? 'Registering...' : 'Register as Transport Provider'}
          </button>
          <p className="text-xs text-[#AAAAAA] text-center mt-3">
            Your details will be used to match you with cooperative logistics jobs across Ghana.
          </p>
        </div>
      </form>
    </div>
  )
}
