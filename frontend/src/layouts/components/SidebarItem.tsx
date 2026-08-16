import { Text, Tooltip } from '@mantine/core'
import { NavLink } from 'react-router-dom'

import type { LucideIcon } from 'lucide-react'

import classes from './SidebarItem.module.css'

interface SidebarItemProps {
  label: string
  icon: LucideIcon
  to: string
  active: boolean
  collapsed: boolean
  onNavigate: () => void
}

const SidebarItem = ({
  label,
  icon: Icon,
  to,
  active,
  collapsed,
  onNavigate,
}: SidebarItemProps) => {
  const link = (
    <NavLink
      to={to}
      onClick={onNavigate}
      // aria-label always set (not just when collapsed) so the
      // accessible name stays identical in both states - when
      // expanded it just mirrors the visible Text below.
      aria-label={label}
      className={`${classes.root} ${active ? classes.active : ''} ${
        collapsed ? classes.collapsed : ''
      }`}
    >
      <Icon size={18} />

      {!collapsed && (
        <Text
          size="sm"
          fw={active ? 600 : 500}
        >
          {label}
        </Text>
      )}
    </NavLink>
  )

  if (!collapsed) {
    return link
  }

  // Labels are hidden when collapsed, so the tooltip is what keeps
  // each icon-only item identifiable.
  return (
    <Tooltip
      label={label}
      position="right"
      withArrow
      openDelay={200}
    >
      {link}
    </Tooltip>
  )
}

export default SidebarItem