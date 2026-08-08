import {
  Box,
  Stack,
} from '@mantine/core'

import {
  Boxes,
  Factory,
  FileBarChart,
  ReceiptText,
  LayoutDashboard,
  Package,
  HistoryIcon,
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
    path: '/forecast',
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