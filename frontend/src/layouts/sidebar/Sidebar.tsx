import {
  Box,
  Divider,
  Stack,
  Text,
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
  TrendingUp,
} from 'lucide-react'

import { useLocation } from 'react-router-dom'

import SidebarItem from '../components/SidebarItem'
import SidebarFooter from './SidebarFooter'

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
    path: '/demand-forecasting',
  },
]

interface SidebarProps {
  onNavigate: () => void
}

const Sidebar = ({
  onNavigate,
}: SidebarProps) => {
  const location = useLocation()

  const isMobile = useMediaQuery(
    '(max-width: 48em)',
  )

  return (
    <Box h="100%" p="md">
      <Stack
        h="100%"
        justify="space-between"
      >
        {/* TOP */}
        <Stack gap="xs">
          {menus.map((item) => (
            <SidebarItem
              key={item.path}
              label={item.label}
              icon={item.icon}
              to={item.path}
              active={
                location.pathname === item.path
              }
              onNavigate={onNavigate}
            />
          ))}
        </Stack>

        {/* BOTTOM */}
        <Stack gap="md">
          {isMobile && (
            <>
              <Divider />

              <Text
                size="sm"
                fw={600}
                c="dimmed"
              >
                Appearance
              </Text>

              <ThemeSwitcher />
            </>
          )}

          <SidebarFooter />
        </Stack>
      </Stack>
    </Box>
  )
}

export default Sidebar