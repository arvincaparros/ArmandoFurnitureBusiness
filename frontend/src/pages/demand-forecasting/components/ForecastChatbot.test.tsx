import { fireEvent, render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it, vi } from 'vitest'

import ForecastChatbot from './ForecastChatbot'
import { ThemeProvider } from '../../../theme/ThemeContext'

import type { ChatMessage } from '../types'

const renderChatbot = (messages: ChatMessage[] = []) => {
  const onSend = vi.fn()

  const view = render(
    <MantineProvider>
      <ThemeProvider>
        <ForecastChatbot
          messages={messages}
          onSend={onSend}
          isSending={false}
          sendError={null}
        />
      </ThemeProvider>
    </MantineProvider>,
  )

  const textarea = screen.getByRole(
    'textbox',
  ) as HTMLTextAreaElement

  // The send control is the last of the input row's icon buttons; it
  // has no visible text, so it is resolved through its icon.
  const sendButton = () =>
    view.container
      .querySelector('.lucide-send')
      ?.closest('button') as HTMLButtonElement | null

  return { onSend, textarea, sendButton }
}

const typeMessage = (
  textarea: HTMLTextAreaElement,
  value: string,
) => {
  fireEvent.change(textarea, { target: { value } })
}

describe('ForecastChatbot message input', () => {
  it('renders a multiline textarea instead of a single-line input', () => {
    const { textarea } = renderChatbot()

    expect(textarea.tagName).toBe('TEXTAREA')

    // A textarea wraps long text by default; the value itself stays
    // intact rather than being truncated at the visible width.
    const longMessage = 'a'.repeat(400)

    typeMessage(textarea, longMessage)

    expect(textarea.value).toBe(longMessage)
  })

  it('inserts a newline on Shift+Enter without sending', () => {
    const { onSend, textarea } = renderChatbot()

    typeMessage(textarea, 'first line')

    fireEvent.keyDown(textarea, {
      key: 'Enter',
      shiftKey: true,
    })

    expect(onSend).not.toHaveBeenCalled()
    // The draft is untouched, so the user can keep typing.
    expect(textarea.value).toBe('first line')
  })

  it('sends on Enter without Shift and clears the input', () => {
    const { onSend, textarea, sendButton } = renderChatbot()

    typeMessage(textarea, 'Which product has the highest demand?')

    fireEvent.keyDown(textarea, { key: 'Enter' })

    expect(onSend).toHaveBeenCalledTimes(1)
    expect(onSend).toHaveBeenCalledWith(
      'Which product has the highest demand?',
    )
    expect(textarea.value).toBe('')

    // A cleared draft leaves the send button disabled again.
    expect(sendButton()).toBeDisabled()
  })

  it('submits a multiline message with its line breaks intact', () => {
    const { onSend, textarea } = renderChatbot()

    const multiline = 'Compare these products:\n- Test Chair\n- Test Table'

    typeMessage(textarea, multiline)

    fireEvent.keyDown(textarea, { key: 'Enter' })

    expect(onSend).toHaveBeenCalledWith(multiline)
  })

  it('keeps the send control usable while the input holds text', () => {
    const { onSend, textarea, sendButton } = renderChatbot()

    expect(sendButton()).toBeDisabled()

    typeMessage(textarea, 'Hello')

    expect(sendButton()).toBeEnabled()

    fireEvent.click(sendButton() as HTMLButtonElement)

    expect(onSend).toHaveBeenCalledWith('Hello')
  })
})
