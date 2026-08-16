import { useEffect, useState } from 'react'

import { Avatar, Center, Stack, Text, Tooltip } from '@mantine/core'

import { useAuth } from '../../auth/AuthContext'
import { useThemeMode } from '../../theme/ThemeContext'
import { getUserInitials } from '../../utils/userInitials'

interface SidebarFooterProps {
  collapsed: boolean
}

const SidebarFooter = ({ collapsed }: SidebarFooterProps) => {
  const { user } = useAuth()
  const { mode } = useThemeMode()

  const [currentDate, setCurrentDate] =
    useState(new Date())

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentDate(new Date())
    }, 60_000)

    return () => clearInterval(interval)
  }, [])

  const formattedDate =
    currentDate.toLocaleDateString(
      'en-US',
      {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      },
    )

  const formattedTime =
    currentDate.toLocaleTimeString(
      'en-US',
      {
        hour: 'numeric',
        minute: '2-digit',
      },
    )

  const username = user?.username ?? 'Guest'

  if (collapsed) {
    return (
      <Center>
        <Tooltip
          label={`${username} - ${formattedDate}, ${formattedTime}`}
          position="right"
          withArrow
        >
          <Avatar
            radius="xl"
            color={mode === 'wood' ? 'wood' : 'blue'}
          >
            {getUserInitials(user?.username)}
          </Avatar>
        </Tooltip>
      </Center>
    )
  }

  return (
    <Stack gap={2}>
      <Text size="sm" fw={600}>
        User: {username}
      </Text>

      <Text size="xs" c="dimmed">
        {formattedDate}
      </Text>

      <Text size="xs" c="dimmed">
        {formattedTime}
      </Text>
    </Stack>
  )
}

export default SidebarFooter
