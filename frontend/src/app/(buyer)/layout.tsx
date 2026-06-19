import BuyerNav from '@/components/buyer/BuyerNav'

export default function BuyerLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-[#EAEDED]">
      <BuyerNav />
      <main className="flex-1">{children}</main>
      <footer className="bg-[#131921] text-[#CCCCCC] text-xs text-center py-4 mt-8">
        <p className="mb-1 font-semibold text-white">AgriMatch Ghana</p>
        <p>Ghana&apos;s Agricultural Intelligence Platform &middot; Powered by AI price forecasting</p>
      </footer>
    </div>
  )
}
