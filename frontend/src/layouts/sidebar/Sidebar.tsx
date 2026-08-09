import {
  Box,
  Divider,
  Group,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core'

import { useMediaQuery } from '@mantine/hooks'

import ThemeSwitcher from '../../theme/ThemeSwitcher'

import {
  Boxes,
  Factory,
  FileBarChart,
  ReceiptText,
  LayoutDashboard,
  Package,
  HistoryIcon,
  User,
  Settings,
  LogOut,
  TrendingUp,
} from 'lucide-react'

import { useLocation } from 'react-router-dom'

import SidebarItem from '../components/SidebarItem'

const menus = [
  {
    label: 'Dashboard',
    icon: LayoutDashboard,
    path: '/dashboard',
  },
  {
    label: 'Resources Management',
    icon: Boxes,
    path: '/resources',
  },
  {
    label: 'Product Data Management',
    icon: Package,
    path: '/products',
  },
  {
    label: 'Production Allocation',
    icon: Factory,
    path: '/production',
  },
  {
    label: 'Resource Utilization Reports',
    icon: FileBarChart,
    path: '/reports',
  },
  {
    label: 'Transaction History',
    icon: ReceiptText,
    path: '/history',
  },
  {
    label: 'Optimization History',
    icon: HistoryIcon,
    path: '/optimization-history',
  },
  {
    label: 'Demand Forecasting',
    icon: TrendingUp,
    path: '/demand-forecasting'
  },
]

const Sidebar = () => {
  const location = useLocation()

  const isMobile = useMediaQuery(
    '(max-width: 48em)',
  )

  return (
    <Box h="100%" p="md">
      <Stack gap={6}>
        {menus.map((item) => (
          <SidebarItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            to={item.path}
            active={
              location.pathname === item.path
            }
          />
        ))}

        {isMobile && (
          <>
            <Divider my="md" />

            <Text
              size="sm"
              fw={600}
              c="dimmed"
              mb="xs"
            >
              Appearance
            </Text>

            <ThemeSwitcher />

            <Divider my="md" />

            <Text
              size="sm"
              fw={600}
              c="dimmed"
              mb="xs"
            >
              Account
            </Text>

            <UnstyledButton>
              <Group gap="sm">
                <User size={18} />
                <Text size="sm">
                  Profile
                </Text>
              </Group>
            </UnstyledButton>

            <UnstyledButton mt="sm">
              <Group gap="sm">
                <Settings size={18} />
                <Text size="sm">
                  Settings
                </Text>
              </Group>
            </UnstyledButton>

            <Divider my="sm" />

            <UnstyledButton>
              <Group gap="sm">
                <LogOut
                  size={18}
                  color="red"
                />

                <Text
                  size="sm"
                  c="red"
                >
                  Logout
                </Text>
              </Group>
            </UnstyledButton>
          </>
        )}
      </Stack>
    </Box>
  )
}

export default Sidebar