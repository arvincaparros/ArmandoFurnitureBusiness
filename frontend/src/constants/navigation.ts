import {
  Boxes,
  Factory,
  FileBarChart,
  History,
  LayoutDashboard,
  Package,
  TrendingUp,
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