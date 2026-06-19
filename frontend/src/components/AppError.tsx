'use client'

import { useEffect } from 'react'

interface AppErrorProps {
  error: Error & { digest?: string }
  reset: () => void
  title?: string
  accentColor?: string
}

export default function AppError({
  error,
  reset,
  title = 'Something went wrong',
  accentColor = '#16a34a',
}: AppErrorProps) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="text-5xl mb-4">⚠️</div>
        <h2 className="text-xl font-semibold text-gray-800 mb-2">{title}</h2>
        <p className="text-gray-500 text-sm mb-2">
          {error.message || 'An unexpected error occurred. Please try again.'}
        </p>
        {error.digest && (
          <p className="text-xs text-gray-400 font-mono mb-4">Ref: {error.digest}</p>
        )}
        <button
          onClick={reset}
          style={{ backgroundColor: accentColor }}
          className="px-5 py-2 text-white text-sm rounded-lg hover:opacity-90 transition-opacity"
        >
          Try again
        </button>
      </div>
    </div>
  )
}
