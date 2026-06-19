'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'

export function QueryProvider({ children }: { children: React.ReactNode }) {
  // useState ensures each browser session gets its own QueryClient instance
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime:          60_000,   // data is fresh for 1 minute
        retry:              1,
        refetchOnWindowFocus: false,
      },
    },
  }))

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
