'use client'

import AppError from '@/components/AppError'

export default function SellerError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return <AppError error={error} reset={reset} />
}
