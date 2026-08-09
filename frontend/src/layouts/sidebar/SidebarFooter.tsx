import { useEffect, useState } from 'react'

import { Stack, Text } from '@mantine/core'

const SidebarFooter = () => {
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

  return (
    <Stack gap={2}>
      <Text size="sm" fw={600}>
        User: Arvin Caparros
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