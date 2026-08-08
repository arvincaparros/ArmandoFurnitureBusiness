import {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react'

type ThemeMode = 'classic' | 'wood'

interface ThemeContextValue {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
  toggleTheme: () => void
}

const ThemeContext =
  createContext<ThemeContextValue | null>(null)

export function ThemeProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [mode, setMode] =
    useState<ThemeMode>('classic')

  useEffect(() => {
    const saved =
      localStorage.getItem('theme') as ThemeMode | null

    if (saved) {
      setMode(saved)
      document.documentElement.setAttribute(
        'data-theme',
        saved,
      )
    }
  }, [])

  useEffect(() => {
    document.documentElement.setAttribute(
      'data-theme',
      mode,
    )

    localStorage.setItem('theme', mode)
  }, [mode])

  const toggleTheme = () => {
    setMode(
      mode === 'classic'
        ? 'wood'
        : 'classic',
    )
  }

  return (
    <ThemeContext.Provider
      value={{
        mode,
        setMode,
        toggleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  )
}

export function useThemeMode() {
  const context = useContext(ThemeContext)

  if (!context) {
    throw new Error(
      'useThemeMode must be used inside ThemeProvider',
    )
  }

  return context
}