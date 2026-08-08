import type { PropsWithChildren } from 'react'

import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import {
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'

import {
  classicTheme,
  woodTheme,
} from '../theme'

import {
  ThemeProvider,
  useThemeMode,
} from '../theme/ThemeContext'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5,
    },
    mutations: {
      retry: 1,
    },
  },
})

const AppThemeProvider = ({
  children,
}: PropsWithChildren) => {
  const { mode } = useThemeMode()

  return (
    <MantineProvider
      theme={
        mode === 'wood'
          ? woodTheme
          : classicTheme
      }
    >
      <Notifications position="top-right" />
      {children}
    </MantineProvider>
  )
}

const Providers = ({
  children,
}: PropsWithChildren) => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AppThemeProvider>
          {children}
        </AppThemeProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default Providers