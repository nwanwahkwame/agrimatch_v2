export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white flex flex-col">
      <main className="flex-1">{children}</main>
      <footer className="border-t border-[#DDDDDD] py-6 mt-4">
        <div className="max-w-sm mx-auto flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-[#565959]">
          <a href="#" className="hover:underline hover:text-[#15803D]">Conditions of Use</a>
          <a href="#" className="hover:underline hover:text-[#15803D]">Privacy Notice</a>
          <a href="#" className="hover:underline hover:text-[#15803D]">Help</a>
        </div>
        <p className="text-center text-xs text-[#767676] mt-2">
          &copy; 2026 AgriMatch Ghana. All rights reserved.
        </p>
      </footer>
    </div>
  )
}
