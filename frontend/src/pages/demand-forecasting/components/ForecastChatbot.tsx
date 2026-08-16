import { useEffect, useRef, useState } from 'react'

import {
  ActionIcon,
  Alert,
  Box,
  Group,
  Loader,
  Paper,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core'

import { AlertCircle, Mic, MicOff, Send } from 'lucide-react'

import { getApiErrorMessage } from '../../../api/apiError'

import ChatMarkdown from './ChatMarkdown'

import type { ChatMessage } from '../types'

// The Web Speech API's SpeechRecognition interface (and its
// non-standard `webkit`-prefixed alias, still required by Chrome)
// aren't declared in this project's lib.dom.d.ts - only the related
// event types (SpeechRecognitionEvent, etc.) are. This is a minimal
// local ambient declaration covering just what's used below, not a
// full spec typing.
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
}

// BCP-47 tags accepted by the Web Speech API. Filipino is default
// since Armando Furniture's staff primarily speak Tagalog/Filipino -
// English remains selectable for mixed/English-only speech.
const SPEECH_LANGUAGE_META: Record<
  string,
  { flag: string; label: string }
> = {
  'fil-PH': { flag: '🇵🇭', label: 'Filipino' },
  'en-US': { flag: '🇺🇸', label: 'English' },
}

interface ForecastChatbotProps {
  messages: ChatMessage[]
  onSend: (message: string) => void
  isSending: boolean
  sendError: unknown
}

const ForecastChatbot = ({
  messages,
  onSend,
  isSending,
  sendError,
}: ForecastChatbotProps) => {
  const [message, setMessage] = useState('')
  const [isListening, setIsListening] = useState(false)
  const [speechError, setSpeechError] = useState<string | null>(null)
  const [speechLang, setSpeechLang] = useState<string>('fil-PH')
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)

  const isSpeechSupported =
    typeof window !== 'undefined' &&
    (window.SpeechRecognition ?? window.webkitSpeechRecognition) !==
      undefined

  const handleSend = () => {
    if (!message.trim() || isSending) return

    onSend(message)
    setMessage('')
  }

  // Stop any in-flight recognition session on unmount so it doesn't
  // keep the microphone active after the user navigates away.
  useEffect(() => {
    return () => {
      recognitionRef.current?.stop()
    }
  }, [])

  const handleToggleLanguage = () => {
    setSpeechLang((current) =>
      current === 'fil-PH' ? 'en-US' : 'fil-PH',
    )
  }

  const handleMicClick = () => {
    if (isListening) {
      recognitionRef.current?.stop()
      return
    }

    const RecognitionCtor =
      window.SpeechRecognition ?? window.webkitSpeechRecognition

    if (!RecognitionCtor) {
      setSpeechError(
        'Speech recognition is not supported in this browser.',
      )
      return
    }

    setSpeechError(null)

    const recognition = new RecognitionCtor()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = speechLang

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? '')
        .join(' ')
        .trim()

      if (transcript) {
        // Populate the existing input for review/edit - never send
        // automatically.
        setMessage((current) =>
          current ? `${current} ${transcript}` : transcript,
        )
      }
    }

    recognition.onerror = (event) => {
      setSpeechError(
        event.error === 'not-allowed'
          ? 'Microphone access was denied.'
          : 'Speech recognition failed. Please try again.',
      )
      setIsListening(false)
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognitionRef.current = recognition
    setIsListening(true)
    recognition.start()
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
                  style={{
                    overflowWrap: 'anywhere',
                    // User bubbles use the app's current primary
                    // color (blue under the Classic theme, wood/brown
                    // under the Wood theme - swapped by
                    // AppThemeProvider in app/providers.tsx, so this
                    // CSS variable is already theme-reactive with no
                    // extra logic here) with white text. Assistant
                    // bubbles use Mantine's own light-gray/text
                    // tokens, unaffected by the active theme.
                    backgroundColor:
                      item.role === 'user'
                        ? 'var(--mantine-primary-color-filled)'
                        : 'var(--mantine-color-gray-1)',
                    color:
                      item.role === 'user'
                        ? '#FFFFFF'
                        : 'var(--mantine-color-text)',
                  }}
                >
                  {item.role === 'assistant' ? (
                    <ChatMarkdown
                      content={item.message}
                    />
                  ) : (
                    <Text size="sm" c="inherit">
                      {item.message}
                    </Text>
                  )}
                </Paper>
              </Group>
            ))}

            {isSending && (
              <Group justify="flex-start">
                <Paper
                  p="sm"
                  radius="md"
                  withBorder
                >
                  <Loader size="xs" type="dots" />
                </Paper>
              </Group>
            )}
          </Stack>
        </ScrollArea>

        {sendError !== null && sendError !== undefined && (
          <Alert
            color="red"
            icon={<AlertCircle size={16} />}
            py={6}
          >
            {getApiErrorMessage(
              sendError,
              'Unable to reach the forecasting assistant. Please try again.',
            )}
          </Alert>
        )}

        {speechError !== null && (
          <Alert
            color="red"
            icon={<AlertCircle size={16} />}
            py={6}
          >
            {speechError}
          </Alert>
        )}

        <Group
          gap="xs"
          align="flex-end"
        >
          <TextInput
            placeholder={
              isListening
                ? 'Listening...'
                : 'Ask about demand forecasts...'
            }
            value={message}
            disabled={isSending}
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

          {isSpeechSupported && (
            <Tooltip label={SPEECH_LANGUAGE_META[speechLang].label}>
              <ActionIcon
                aria-label="Toggle speech recognition language"
                variant="default"
                size="lg"
                w={40}
                onClick={handleToggleLanguage}
                disabled={isListening || isSending}
              >
                <Text size="lg" style={{ lineHeight: 1 }}>
                  {SPEECH_LANGUAGE_META[speechLang].flag}
                </Text>
              </ActionIcon>
            </Tooltip>
          )}

          <Tooltip
            label={
              isSpeechSupported
                ? isListening
                  ? 'Stop listening'
                  : 'Speak your question'
                : 'Speech recognition is not supported in this browser'
            }
          >
            <ActionIcon
              variant={isListening ? 'filled' : 'default'}
              color={isListening ? 'red' : 'wood'}
              size="lg"
              onClick={handleMicClick}
              disabled={isSending || !isSpeechSupported}
            >
              {isListening ? (
                <MicOff size={18} />
              ) : (
                <Mic size={18} />
              )}
            </ActionIcon>
          </Tooltip>

          <ActionIcon
            variant='default'
            color="wood"
            size="lg"
            onClick={handleSend}
            disabled={!message.trim() || isSending}
            loading={isSending}
          >
            <Send size={18} />
          </ActionIcon>
        </Group>
      </Stack>
    </Paper>
  )
}

export default ForecastChatbot
