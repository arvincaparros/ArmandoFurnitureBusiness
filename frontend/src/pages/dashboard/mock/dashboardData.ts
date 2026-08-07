import {
  Boxes,
  Factory,
  Package,
  TrendingUp,
} from 'lucide-react'

import type {
  DashboardStat,
  ProductionTrend,
  ResourceUsage,
  RecentActivity,
} from '../types'

export const dashboardStats: DashboardStat[] = [
  {
    id: 'products',
    title: 'Products',
    value: 125,
    description: '12 new this month',
    icon: Package,
    color: 'blue',
  },
  {
    id: 'resources',
    title: 'Resources',
    value: 58,
    description: 'Available inventory',
    icon: Boxes,
    color: 'green',
  },
  {
    id: 'production',
    title: 'Production',
    value: 320,
    description: 'Completed today',
    icon: Factory,
    color: 'orange',
  },
  {
    id: 'efficiency',
    title: 'Efficiency',
    value: '95%',
    description: 'Production efficiency',
    icon: TrendingUp,
    color: 'teal',
  },
]

export const productionTrend: ProductionTrend[] = [
  { month: 'Jan', production: 120 },
  { month: 'Feb', production: 145 },
  { month: 'Mar', production: 170 },
  { month: 'Apr', production: 190 },
  { month: 'May', production: 220 },
  { month: 'Jun', production: 250 },
]

export const resourceUsage: ResourceUsage[] = [
  { name: 'Wood', value: 40 },
  { name: 'Steel', value: 25 },
  { name: 'Fabric', value: 20 },
  { name: 'Foam', value: 15 },
]

export const recentActivities: RecentActivity[] = [
  {
    id: '1',
    activity: 'New production schedule created',
    user: 'Admin',
    date: 'Today',
  },
  {
    id: '2',
    activity: 'Inventory updated',
    user: 'Warehouse',
    date: 'Yesterday',
  },
]