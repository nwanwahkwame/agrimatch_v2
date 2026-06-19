'use client'

import AppError from '@/components/AppError'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body className="min-h-screen flex items-center justify-center bg-gray-50 p-8">
        <AppError error={error} reset={reset} title="Unexpected error" />
      </body>
    </html>
  )
}
