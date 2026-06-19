import SellerNav from '@/components/seller/SellerNav'

export default function SellerLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[#F3F3F3]">
      <SellerNav />
      <main className="flex-1 min-w-0 pb-16 md:pb-0">{children}</main>
    </div>
  )
}
