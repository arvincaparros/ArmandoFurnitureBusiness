import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { sendForecastChatMessage } from '../api/forecastApi'

import type { ChatMessage } from '../types'

// A short, honest UI label - not a claim of having "analyzed" anything
// (the old mock greeting fabricated that). Real conversation starts
// empty otherwise; nothing here is forecast data.
const GREETING: ChatMessage = {
  id: 0,
  role: 'assistant',
  message:
    "Ask me a question about your demand forecast - for example, which products have the highest predicted demand or the lowest confidence.",
}

// In-memory only, per approved product decision - conversation resets
// on refresh/navigation, no persistence, no new backend table. Kept
// as its own hook (separate from useForecast.ts) since chat is an
// independent concern from the forecast table/chart/generate flow -
// switching the chart's selected product must not affect this state,
// and it doesn't, since nothing here reads selectedProductId.
const useForecastChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    GREETING,
  ])

  const nextId = useRef(1)

  const sendMutation = useMutation({
    mutationFn: sendForecastChatMessage,
  })

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()

    if (!trimmed || sendMutation.isPending) {
      return
    }

    setMessages((prev) => [
      ...prev,
      {
        id: nextId.current++,
        role: 'user',
        message: trimmed,
      },
    ])

    try {
      const { reply } = await sendMutation.mutateAsync(trimmed)

      setMessages((prev) => [
        ...prev,
        {
          id: nextId.current++,
          role: 'assistant',
          message: reply,
        },
      ])
    } catch {
      // Failure is surfaced via sendError below - no fake assistant
      // message is appended when the backend/AI call fails.
    }
  }

  return {
    messages,
    sendMessage,
    isSending: sendMutation.isPending,
    sendError: sendMutation.error,
  }
}

export default useForecastChat
