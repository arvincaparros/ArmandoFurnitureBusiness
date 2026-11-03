import {
  Boxes,
  ClipboardCheck,
  Factory,
  FileBarChart,
  History,
  LayoutDashboard,
  Package,
  TrendingUp,
  Warehouse,
} from 'lucide-react'

import type { LucideIcon } from 'lucide-react'

export interface NavigationItem {
  label: string
  path: string
  icon: LucideIcon
}

export const navigation: NavigationItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    label: 'Resources',
    path: '/resources',
    icon: Boxes,
  },
  {
    label: 'Products',
    path: '/products',
    icon: Package,
  },
  {
    label: 'Production',
    path: '/production',
    icon: Factory,
  },
  {
    label: 'Opening Stock',
    path: '/opening-inventory',
    icon: ClipboardCheck,
  },
  {
    label: 'Inventory',
    path: '/inventory',
    icon: Warehouse,
  },
  {
    label: 'Forecast',
    path: '/forecast',
    icon: TrendingUp,
  },
  {
    label: 'Reports',
    path: '/reports',
    icon: FileBarChart,
  },
  {
    label: 'History',
    path: '/history',
    icon: History,
  },
]