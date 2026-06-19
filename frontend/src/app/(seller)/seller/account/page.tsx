'use client'

import { useState, useEffect } from 'react'
import { User, Phone, Mail, MapPin, Bell, Shield, CheckCircle, Hash } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { farmerDbId } from '@/lib/auth'
import { getAdminDistricts } from '@/lib/api'

export default function SellerAccountPage() {
  const { user }                  = useAuth()
  const farmerId                  = farmerDbId(user)
  const [districtName, setDistrictName] = useState('—')

  useEffect(() => {
    if (!user?.districtId) return
    getAdminDistricts()
      .then(r => {
        const d = (r.data as { id: number; district: string }[]).find(x => x.id === user.districtId)
        if (d) setDistrictName(d.district)
      })
      .catch(() => {})
  }, [user?.districtId])

  const [priceAlerts,     setPriceAlerts]     = useState(true)
  const [csiAlerts,       setCsiAlerts]       = useState(true)
  const [logisticsAlerts, setLogisticsAlerts] = useState(false)
  const [saved, setSaved] = useState(false)

  function handleSave() {
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  const initials = (user?.name ?? 'F')
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <div className="p-4 sm:p-6 max-w-2xl mx-auto pb-20 md:pb-6">
      <h1 className="text-xl font-bold text-[#0F1111] mb-1">Account</h1>
      <p className="text-sm text-[#565959] mb-6">Your profile and notification preferences</p>

      {/* Profile card */}
      <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden mb-5">
        <div className="bg-[#232F3E] px-5 py-4 flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-[#22C55E] flex items-center justify-center shrink-0">
            <span className="text-xl font-bold text-white">{initials}</span>
          </div>
          <div>
            <p className="text-white font-bold text-base">{user?.name ?? 'Farmer'}</p>
            <p className="text-[#CCCCCC] text-xs">
              Farmer ID #{farmerId}
              {user?.farmerId ? ` · ${user.farmerId}` : ''}
            </p>
          </div>
        </div>

        <div className="divide-y divide-[#EEEEEE]">
          {[
            { icon: User,   label: 'Full name',       value: user?.name     ?? '—' },
            { icon: Phone,  label: 'Phone number',    value: user?.phone    ? `+233 ${user.phone.replace(/^0/, '')}` : '—' },
            { icon: Mail,   label: 'Email',           value: user?.email    ?? '—' },
            { icon: Hash,   label: 'Farmer ID',       value: user?.farmerId ?? `#${farmerId}` },
            { icon: MapPin, label: 'District',        value: districtName  },
          ].map(({ icon: Icon, label, value }) => (
            <div key={label} className="flex items-center gap-4 px-5 py-3.5">
              <Icon className="h-4 w-4 text-[#565959] shrink-0" />
              <div className="flex-1">
                <p className="text-xs text-[#565959]">{label}</p>
                <p className="text-sm font-medium text-[#0F1111]">{value}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Notification preferences */}
      <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden mb-5">
        <div className="px-5 py-3.5 border-b border-[#EEEEEE] flex items-center gap-2">
          <Bell className="h-4 w-4 text-[#565959]" />
          <h2 className="font-semibold text-sm text-[#0F1111]">Notification preferences</h2>
        </div>
        <div className="divide-y divide-[#EEEEEE]">
          {[
            { label: 'Price alerts',            sub: 'Notify when forecast prices change significantly',         value: priceAlerts,     toggle: setPriceAlerts     },
            { label: 'Climate stress (CSI)',    sub: 'Alert when drought or extreme weather detected nearby',    value: csiAlerts,       toggle: setCsiAlerts       },
            { label: 'Logistics group alerts',  sub: 'Notify when a shared truck group forms near me',          value: logisticsAlerts, toggle: setLogisticsAlerts },
          ].map(({ label, sub, value, toggle }) => (
            <div key={label} className="flex items-center justify-between gap-4 px-5 py-4">
              <div>
                <p className="text-sm font-medium text-[#0F1111]">{label}</p>
                <p className="text-xs text-[#565959] mt-0.5">{sub}</p>
              </div>
              <button
                onClick={() => toggle(v => !v)}
                className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${value ? 'bg-[#22C55E]' : 'bg-[#CCCCCC]'}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${value ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Security */}
      <div className="bg-white rounded-lg border border-[#DDDDDD] overflow-hidden mb-6">
        <div className="px-5 py-3.5 border-b border-[#EEEEEE] flex items-center gap-2">
          <Shield className="h-4 w-4 text-[#565959]" />
          <h2 className="font-semibold text-sm text-[#0F1111]">Account security</h2>
        </div>
        <div className="px-5 py-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-[#0F1111]">
              {user?.phone ? 'Phone verification' : 'Email verification'}
            </p>
            <p className="text-xs text-[#565959] mt-0.5">
              {user?.phone
                ? 'Your phone number is verified via USSD'
                : 'Your email address is verified'}
            </p>
          </div>
          <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-100 px-2.5 py-1 rounded-full">
            <CheckCircle className="h-3 w-3" /> Verified
          </span>
        </div>
      </div>

      <button
        onClick={handleSave}
        className={`w-full rounded-lg py-3 text-sm font-bold transition-colors ${
          saved ? 'bg-[#1D6B3A] text-white' : 'bg-[#22C55E] hover:bg-[#16A34A] text-white'
        }`}
      >
        {saved ? (
          <span className="flex items-center justify-center gap-2">
            <CheckCircle className="h-4 w-4" /> Preferences saved
          </span>
        ) : 'Save preferences'}
      </button>
    </div>
  )
}
