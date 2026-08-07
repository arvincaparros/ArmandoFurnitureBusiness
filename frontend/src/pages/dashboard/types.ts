import type { LucideIcon } from 'lucide-react'

export interface DashboardStat {
  id: string
  title: string
  value: string | number
  description?: string
  color?: string
  icon: LucideIcon
}

export interface ProductionTrend {
  month: string
  production: number
}

export interface ResourceUsage {
  name: string
  value: number
}

export interface RecentActivity {
  id: string
  activity: string
  user: string
  date: string
}