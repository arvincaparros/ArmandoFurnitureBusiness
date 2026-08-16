import {
  Box,
  Divider,
  Group,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'

import { useMediaQuery } from '@mantine/hooks'

import ThemeSwitcher from '../../theme/ThemeSwitcher'

import {
  Boxes,
  Factory,
  FileBarChart,
  FileClock,
  ReceiptText,
  LayoutDashboard,
  Package,
  HistoryIcon,
  PanelLeftClose,
  PanelLeftOpen,
  TrendingUp,
} from 'lucide-react'

import { useLocation } from 'react-router-dom'

import SidebarItem from '../components/SidebarItem'
import SidebarFooter from './SidebarFooter'
import { useSidebarCollapsed } from '../SidebarContext'

import classes from './Sidebar.module.css'

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
    label: 'Resource Utilization History',
    icon: FileClock,
    path: '/resource-utilization-history',
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

  const {
    effectiveCollapsed,
    isDesktop,
    toggleCollapsed,
  } = useSidebarCollapsed()

  const toggleLabel = effectiveCollapsed
    ? 'Expand sidebar'
    : 'Collapse sidebar'

  const [dashboardItem, ...otherItems] = menus

  const dashboardLink = (
    <SidebarItem
      label={dashboardItem.label}
      icon={dashboardItem.icon}
      to={dashboardItem.path}
      active={location.pathname === dashboardItem.path}
      collapsed={effectiveCollapsed}
      onNavigate={onNavigate}
    />
  )

  // Desktop only - the mobile drawer always renders fully expanded,
  // so a collapse toggle has nothing to do there. Same icon/color/
  // hover/radius language as SidebarItem (see Sidebar.module.css),
  // just sized as a compact button instead of a full nav row.
  const collapseToggle = isDesktop && (
    <Tooltip
      label={toggleLabel}
      position="right"
      withArrow
    >
      <UnstyledButton
        className={classes.collapseToggle}
        aria-label={toggleLabel}
        onClick={toggleCollapsed}
      >
        {effectiveCollapsed ? (
          <PanelLeftOpen size={18} />
        ) : (
          <PanelLeftClose size={18} />
        )}
      </UnstyledButton>
    </Tooltip>
  )

  return (
    <Box h="100%" p="md">
      <Stack
        h="100%"
        justify="space-between"
      >
        {/* TOP */}
        <Stack gap="xs">
          {isDesktop && !effectiveCollapsed ? (
            // Expanded: the toggle sits on the same row as Dashboard,
            // right-aligned, so it reads as part of the sidebar's
            // header rather than a separate control.
            <Group
              gap={4}
              wrap="nowrap"
              w="100%"
            >
              <Box style={{ flex: 1, minWidth: 0 }}>
                {dashboardLink}
              </Box>

              {collapseToggle}
            </Group>
          ) : (
            <>
              {isDesktop && (
                <Box
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                  }}
                >
                  {collapseToggle}
                </Box>
              )}

              {dashboardLink}
            </>
          )}

          {otherItems.map((item) => (
            <SidebarItem
              key={item.path}
              label={item.label}
              icon={item.icon}
              to={item.path}
              active={
                location.pathname === item.path
              }
              collapsed={effectiveCollapsed}
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

          <SidebarFooter collapsed={effectiveCollapsed} />
        </Stack>
      </Stack>
    </Box>
  )
}

export default Sidebar
