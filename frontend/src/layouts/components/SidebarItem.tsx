import { Text } from '@mantine/core'
import { NavLink } from 'react-router-dom'

import type { LucideIcon } from 'lucide-react'

import classes from './SidebarItem.module.css'

interface SidebarItemProps {
  label: string
  icon: LucideIcon
  to: string
  active: boolean
}

const SidebarItem = ({
  label,
  icon: Icon,
  to,
  active,
}: SidebarItemProps) => {
  return (
    <NavLink
      to={to}
      className={`${classes.root} ${active ? classes.active : ''}`}
    >
      <Icon size={18} />

      <Text
        size="sm"
        fw={active ? 600 : 500}
      >
        {label}
      </Text>
    </NavLink>
  )
}

export default SidebarItem