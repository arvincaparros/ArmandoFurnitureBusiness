import {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react'

import { useMediaQuery } from '@mantine/hooks'

// Mirrors theme/ThemeContext.tsx's approach (localStorage-backed UI
// preference) - the existing precedent for this kind of persisted
// layout preference in this app. Restored via useState's lazy
// initializer rather than ThemeContext's read-in-an-effect (both
// achieve the same "restore on load" result; the initializer avoids
// an extra render and the react-hooks/set-state-in-effect warning
// that pattern has).
const SIDEBAR_COLLAPSED_STORAGE_KEY = 'sidebar-collapsed'

function getInitialCollapsed(): boolean {
  if (typeof window === 'undefined') {
    return false
  }

  return (
    localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === 'true'
  )
}

interface SidebarContextValue {
  // Raw persisted desktop preference - what AppLayout.tsx's AppShell
  // navbar width reads. Mantine's own responsive width object
  // ({ base, md }) already ignores this below the md breakpoint, so
  // AppLayout doesn't need the viewport-gated value below.
  collapsed: boolean

  // collapsed, but forced false below the same breakpoint AppShell's
  // navbar uses to switch into mobile-drawer mode (md, 62em) - the
  // desktop collapse preference must never visually collapse the
  // mobile drawer. This is what Sidebar.tsx/Header.tsx's Logo use to
  // decide whether to actually hide labels/text (a JS conditional,
  // not a CSS media query, so it needs the viewport already resolved
  // here rather than duplicated in every consumer).
  effectiveCollapsed: boolean

  isDesktop: boolean

  toggleCollapsed: () => void
}

const SidebarContext =
  createContext<SidebarContextValue | null>(null)

export function SidebarProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [collapsed, setCollapsed] = useState(
    getInitialCollapsed,
  )

  useEffect(() => {
    localStorage.setItem(
      SIDEBAR_COLLAPSED_STORAGE_KEY,
      String(collapsed),
    )
  }, [collapsed])

  // Same breakpoint as AppLayout.tsx's AppShell navbar={{ breakpoint:
  // 'md' }} (62em is Mantine's default 'md') - kept in sync so the
  // width prop and this JS-level gate switch at the exact same point.
  const isDesktop = useMediaQuery('(min-width: 62em)') ?? false

  const toggleCollapsed = () => {
    setCollapsed((previous) => !previous)
  }

  return (
    <SidebarContext.Provider
      value={{
        collapsed,
        effectiveCollapsed: collapsed && isDesktop,
        isDesktop,
        toggleCollapsed,
      }}
    >
      {children}
    </SidebarContext.Provider>
  )
}

export function useSidebarCollapsed() {
  const context = useContext(SidebarContext)

  if (!context) {
    throw new Error(
      'useSidebarCollapsed must be used inside SidebarProvider',
    )
  }

  return context
}
