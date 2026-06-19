'use client'

import AppError from '@/components/AppError'

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return <AppError error={error} reset={reset} title="Admin error" accentColor="#0D3D20" />
}
