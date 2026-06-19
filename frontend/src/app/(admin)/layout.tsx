import Link from 'next/link'
import { Leaf, ExternalLink } from 'lucide-react'
import AdminNav from '@/components/admin/AdminNav'
import AdminHeaderClient from '@/components/admin/AdminHeaderClient'

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-[#F7FAF8]">
      <header className="bg-[#0D3D20] px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Leaf className="h-5 w-5 text-[#4DB876]" />
          <span className="font-bold text-white text-sm">AgriMatch</span>
          <span className="text-[#4DB876] text-xs font-medium border border-[#4DB876]/40 rounded px-2 py-0.5 ml-1">
            Admin
          </span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-1.5 text-xs text-[#7DCFA0] hover:text-white transition-colors">
            <ExternalLink className="h-3.5 w-3.5" /> Buyer marketplace
          </Link>
          <AdminHeaderClient />
        </div>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        <AdminNav />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
