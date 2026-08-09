import { AppShell } from '@mantine/core'

import { Outlet } from 'react-router-dom'

import { useDisclosure } from '@mantine/hooks'

import Header from './header/Header'
import Sidebar from './sidebar/Sidebar'

const AppLayout = () => {
  const [opened, { toggle, close }] =
    useDisclosure(false)

  return (
    <AppShell
      header={{
        height: 64,
      }}
      navbar={{
        width: 260,
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

export default AppLayout