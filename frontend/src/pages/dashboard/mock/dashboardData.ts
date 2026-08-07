import {
  Archive,
  DollarSign,
  Trash2,
  TrendingUp,
} from 'lucide-react'

import type {
  DashboardStat,
  RecentActivity,
} from '../types'

export const dashboardStats: DashboardStat[] = [
  {
    id: 'total-resources',
    title: 'Total Available Resources',
    value: '1,248 units',
    description: 'Current inventory',
    icon: Archive,
    color: 'blue',
  },
  {
    id: 'expected-revenue',
    title: 'Expected Revenue',
    value: '₱285,400',
    description: 'Projected sales',
    icon: DollarSign,
    color: 'green',
  },
  {
    id: 'expected-profit',
    title: 'Expected Profit',
    value: '₱96,720',
    description: 'Estimated net profit',
    icon: TrendingUp,
    color: 'orange',
  },
  {
    id: 'waste-percentage',
    title: 'Waste Percentage',
    value: '4.8%',
    description: 'Material waste',
    icon: Trash2,
    color: 'red',
  },
]

export const productionRecommendations = [
  {
    id: 1,
    name: 'Dining Table (6-seater)',
    quantity: '12 units',
    profit: '₱36,000',
  },
  {
    id: 2,
    name: 'Wardrobe Cabinet',
    quantity: '6 units',
    profit: '₱24,000',
  },
  {
    id: 3,
    name: 'Bookshelf',
    quantity: '15 units',
    profit: '₱18,000',
  },
  {
    id: 4,
    name: 'Carved Chair',
    quantity: '24 units',
    profit: '₱18,720',
  },
]

export const resourceUtilization = [
  {
    name: 'Wood',
    value: 33,
  },
  {
    name: 'Labor',
    value: 20,
  },
  {
    name: 'Machine Hours',
    value: 18,
  },
  {
    name: 'Glue',
    value: 8,
  },
  {
    name: 'Nails',
    value: 6,
  },
  {
    name: 'Sandpaper',
    value: 5,
  },
  {
    name: 'Epoxy',
    value: 4,
  },
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