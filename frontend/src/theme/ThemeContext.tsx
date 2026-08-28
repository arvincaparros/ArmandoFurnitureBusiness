import {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react'

type ThemeMode = 'classic' | 'wood'

const THEME_MODES: ThemeMode[] = ['classic', 'wood']

function isThemeMode(value: string | null): value is ThemeMode {
  return value !== null && THEME_MODES.includes(value as ThemeMode)
}

// Reads the saved preference synchronously, during initial state
// computation - not in an effect. This runs once, before the first
// render/paint, so `mode` is correct from the very start and there
// is no window where a stale 'wood' render exists to be persisted
// over a real saved value (see ThemeProvider's single effect below).
// window/localStorage are guarded since useState's initializer runs
// during render, which for this SPA is always client-side, but this
// keeps the function safe if that ever changes.
function readInitialMode(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'wood'
  }

  const saved = window.localStorage.getItem('theme')

  return isThemeMode(saved) ? saved : 'wood'
}

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
    useState<ThemeMode>(readInitialMode)

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