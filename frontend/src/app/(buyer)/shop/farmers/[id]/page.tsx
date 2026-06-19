'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { MapPin, ShieldCheck, ArrowLeft, Package, Star, Calendar } from 'lucide-react'
import API from '@/lib/api'
import { cropImageSrc } from '@/lib/cropImage'

interface Listing {
  id: number
  crop: string
  quantity_kg: number
  harvest_date: string
  price_forecast_ghs: number | null
  csi_flag: string
}

interface FarmerProfile {
  farmer_id: number
  full_name: string
  district: string
  region: string
  member_since: string | null
  completed_sales: number
  active_listings: Listing[]
}

function cropLabel(name: string) {
  return name.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function initials(name: string) {
  return name.split(' ').slice(0, 2).map(w => w[0]?.toUpperCase()).join('')
}

function ListingCard({ l }: { l: Listing }) {
  const bags = Math.round(l.quantity_kg / 100)
  const daysUntil = Math.ceil((new Date(l.harvest_date).getTime() - Date.now()) / 86_400_000)
  return (
    <Link href={`/shop/${l.id}`}
      className="group bg-white rounded border border-[#DDDDDD] hover:shadow-md transition-shadow overflow-hidden flex flex-col">
      <div className="h-40 relative overflow-hidden">
        <Image src={cropImageSrc(l.crop, l.id)} alt={cropLabel(l.crop)} fill className="object-cover group-hover:scale-105 transition-transform duration-300" />
        {l.csi_flag === 'alert' && (
          <span className="absolute top-2 left-2 bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded">Climate Alert</span>
        )}
        {daysUntil <= 7 && daysUntil >= 0 && (
          <span className="absolute top-2 right-2 bg-[#CC0C39] text-white text-[10px] font-bold px-2 py-0.5 rounded">Urgent</span>
        )}
      </div>
      <div className="p-3 flex flex-col flex-1 gap-1">
        <p className="text-sm font-semibold text-[#0F1111] group-hover:text-[#15803D] transition-colors">{cropLabel(l.crop)}</p>
        <p className="text-xs text-[#565959]">{bags} bag{bags !== 1 ? 's' : ''} · {l.quantity_kg.toLocaleString()} kg</p>
        {l.price_forecast_ghs ? (
          <p className="text-base font-bold text-[#0F1111] mt-0.5">GHS {l.price_forecast_ghs.toFixed(2)}<span className="text-xs font-normal text-[#565959]">/kg</span></p>
        ) : (
          <p className="text-xs text-[#565959] mt-0.5">Price on request</p>
        )}
        <div className="flex items-center gap-1 text-xs text-[#007185] mt-0.5">
          <Calendar className="h-3 w-3" />
          {daysUntil <= 0 ? 'Ready now' : daysUntil === 1 ? 'Tomorrow' : `${daysUntil} days`}
        </div>
        <div className="mt-auto pt-2">
          <span className="w-full block text-center bg-[#22C55E] hover:bg-[#16A34A] text-white text-xs font-semibold rounded py-1.5 transition-colors">
            View Listing
          </span>
        </div>
      </div>
    </Link>
  )
}

export default function FarmerProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [profile, setProfile] = useState<FarmerProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(false)

  useEffect(() => {
    API.get(`/api/farmers/${id}/profile`)
      .then(r => setProfile(r.data as FarmerProfile))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="mx-auto max-w-screen-xl px-4 py-8 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-32 mb-6" />
        <div className="flex items-center gap-5 mb-8">
          <div className="h-20 w-20 rounded-full bg-gray-200" />
          <div className="flex flex-col gap-2">
            <div className="h-5 bg-gray-200 rounded w-48" />
            <div className="h-3 bg-gray-200 rounded w-32" />
            <div className="h-3 bg-gray-200 rounded w-24" />
          </div>
        </div>
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-56 bg-gray-200 rounded" />)}
        </div>
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="mx-auto max-w-screen-xl px-4 py-16 text-center">
        <Package className="mx-auto h-16 w-16 text-gray-300 mb-4" />
        <p className="font-bold text-[#0F1111] mb-2">Farmer not found</p>
        <Link href="/shop" className="text-[#007185] hover:underline text-sm">Back to marketplace</Link>
      </div>
    )
  }

  const memberYear = profile.member_since ? new Date(profile.member_since).getFullYear() : null

  return (
    <div className="mx-auto max-w-screen-xl px-4 py-6">

      <Link href="/shop" className="flex items-center gap-1.5 text-sm text-[#007185] hover:underline mb-5">
        <ArrowLeft className="h-4 w-4" /> Back to marketplace
      </Link>

      {/* Farmer header */}
      <div className="bg-white rounded-lg border border-[#DDDDDD] p-6 mb-6">
        <div className="flex items-start gap-5 flex-wrap">
          <div className="h-20 w-20 rounded-full bg-[#1D6B3A] flex items-center justify-center shrink-0">
            <span className="text-white text-2xl font-bold">{initials(profile.full_name)}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <h1 className="text-xl font-bold text-[#0F1111]">{profile.full_name}</h1>
              <span className="flex items-center gap-1 text-xs font-semibold text-[#15803D] bg-[#F0FDF4] border border-[#22C55E]/30 px-2 py-0.5 rounded-full">
                <ShieldCheck className="h-3 w-3" /> Verified Farmer
              </span>
            </div>
            <div className="flex items-center gap-1 text-sm text-[#565959] mb-2">
              <MapPin className="h-4 w-4 shrink-0" />
              <span>{profile.district}, {profile.region} Region</span>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              {memberYear && (
                <span className="text-[#565959]">Member since <strong className="text-[#0F1111]">{memberYear}</strong></span>
              )}
              <span className="text-[#565959]">
                <strong className="text-[#0F1111]">{profile.completed_sales}</strong> completed sale{profile.completed_sales !== 1 ? 's' : ''}
              </span>
              <span className="text-[#565959]">
                <strong className="text-[#0F1111]">{profile.active_listings.length}</strong> active listing{profile.active_listings.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-0.5">
            {[1,2,3,4,5].map(i => (
              <Star key={i} className={`h-4 w-4 ${i <= Math.min(5, Math.max(3, profile.completed_sales > 10 ? 5 : 4)) ? 'fill-[#F59E0B] text-[#F59E0B]' : 'fill-gray-200 text-gray-200'}`} />
            ))}
          </div>
        </div>
      </div>

      {/* Active listings */}
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-lg font-bold text-[#0F1111]">Active Listings</h2>
        {profile.active_listings.length > 0 && (
          <span className="text-xs text-[#565959]">{profile.active_listings.length} listing{profile.active_listings.length !== 1 ? 's' : ''} available</span>
        )}
      </div>

      {profile.active_listings.length === 0 ? (
        <div className="bg-white rounded border border-[#DDDDDD] p-10 text-center">
          <Package className="mx-auto h-12 w-12 text-gray-300 mb-3" />
          <p className="font-semibold text-[#0F1111] mb-1">No active listings</p>
          <p className="text-sm text-[#565959]">This farmer has no active produce listed right now.</p>
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
          {profile.active_listings.map(l => <ListingCard key={l.id} l={l} />)}
        </div>
      )}
    </div>
  )
}
