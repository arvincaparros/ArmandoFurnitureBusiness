import {
  Box,
  Stack,
} from '@mantine/core'

import {
  Boxes,
  Factory,
  FileBarChart,
  History,
  LayoutDashboard,
  Package,
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
    label: 'Resources',
    icon: Boxes,
    path: '/resources',
  },
  {
    label: 'Products',
    icon: Package,
    path: '/products',
  },
  {
    label: 'Production',
    icon: Factory,
    path: '/production',
  },
  {
    label: 'Forecast',
    icon: TrendingUp,
    path: '/forecast',
  },
  {
    label: 'Reports',
    icon: FileBarChart,
    path: '/reports',
  },
  {
    label: 'History',
    icon: History,
    path: '/history',
  },
]

const Sidebar = () => {
  const location = useLocation()

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
      </Stack>
    </Box>
  )
}

export default Sidebar