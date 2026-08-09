import {
  ActionIcon,
  Box,
  Group,
  Paper,
  ScrollArea,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'

import {
  Mic,
  Paperclip,
  Send,
} from 'lucide-react'

import { useState } from 'react'

import type { ChatMessage } from '../types'

interface ForecastChatbotProps {
  messages: ChatMessage[]
}

const ForecastChatbot = ({
  messages,
}: ForecastChatbotProps) => {
  const [message, setMessage] = useState('')

  const handleSend = () => {
    if (!message.trim()) return

    console.log('Send message:', message)

    setMessage('')
  }

  return (
    <Paper
      withBorder
      radius="md"
      p="md"
      h="100%"
    >
      <Stack h="100%" gap="sm">
        <Box>
          <Text fw={600}>
            AI Assistant
          </Text>

          <Text
            size="xs"
            c="dimmed"
          >
            Demand Forecasting Assistant
          </Text>
        </Box>

        <ScrollArea
          style={{ flex: 1 }}
        >
          <Stack gap="sm">
            {messages.map((item) => (
              <Group
                key={item.id}
                justify={
                  item.role === 'user'
                    ? 'flex-end'
                    : 'flex-start'
                }
              >
                <Paper
                  p="sm"
                  radius="md"
                  withBorder
                  maw="85%"
                >
                  <Text size="sm">
                    {item.message}
                  </Text>
                </Paper>
              </Group>
            ))}
          </Stack>
        </ScrollArea>

        <Group
          gap="xs"
          align="flex-end"
        >
          <ActionIcon
            variant="subtle"
            size="lg"
          >
            <Paperclip size={18} />
          </ActionIcon>

          <ActionIcon
            variant="subtle"
            size="lg"
          >
            <Mic size={18} />
          </ActionIcon>

          <TextInput
            placeholder="Ask about demand forecasts..."
            value={message}
            onChange={(event) =>
              setMessage(
                event.currentTarget.value,
              )
            }
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                handleSend()
              }
            }}
            style={{ flex: 1 }}
          />

          

          <ActionIcon
            variant='default'
            color="wood"
            size="lg"
            onClick={handleSend}
          >
            <Send size={18} />
          </ActionIcon>
        </Group>
      </Stack>
    </Paper>
  )
}

export default ForecastChatbot