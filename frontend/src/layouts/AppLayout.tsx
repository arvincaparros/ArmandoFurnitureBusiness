import { AppShell } from '@mantine/core'

import { Outlet } from 'react-router-dom'

import { useDisclosure } from '@mantine/hooks'

import Header from './header/Header'
import Sidebar from './sidebar/Sidebar'
import { SidebarProvider, useSidebarCollapsed } from './SidebarContext'

const SIDEBAR_WIDTH_EXPANDED = 260
const SIDEBAR_WIDTH_COLLAPSED = 80

const AppLayoutContent = () => {
  const [opened, { toggle, close }] =
    useDisclosure(false)

  const { collapsed } = useSidebarCollapsed()

  return (
    <AppShell
      header={{
        height: 64,
      }}
      navbar={{
        // base (mobile) always stays the normal drawer width -
        // the desktop collapsed preference must never shrink the
        // mobile drawer. md matches the breakpoint below, where the
        // desktop collapsed/expanded width actually applies.
        width: {
          base: SIDEBAR_WIDTH_EXPANDED,
          md: collapsed
            ? SIDEBAR_WIDTH_COLLAPSED
            : SIDEBAR_WIDTH_EXPANDED,
        },
        breakpoint: 'md',
        collapsed: {
          mobile: !opened,
        },
      }}
      padding="lg"
      styles={{
        main: {
          background: '#F8FAFC',
        },

        header: {
          borderBottom:
            '1px solid #E2E8F0',
          background: '#FFFFFF',
        },

        navbar: {
          borderRight:
            '1px solid #E2E8F0',
          background: '#FFFFFF',
          transition: 'width 200ms ease',
        },
      }}
    >
      <AppShell.Header>
        <Header
          opened={opened}
          toggle={toggle}
        />
      </AppShell.Header>

      <AppShell.Navbar>
        <Sidebar onNavigate={close} />
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}

const AppLayout = () => (
  <SidebarProvider>
    <AppLayoutContent />
  </SidebarProvider>
)

export default AppLayout
