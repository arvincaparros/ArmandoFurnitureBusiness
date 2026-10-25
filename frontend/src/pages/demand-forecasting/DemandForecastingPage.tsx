import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
} from 'react'
import { Link } from 'react-router-dom'

import {
  ActionIcon,
  Alert,
  Anchor,
  Box,
  Group,
  Select,
  Text,
} from '@mantine/core'
import { AlertCircle, Bot, Info, X } from 'lucide-react'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import ForecastToolbar from './components/ForecastToolbar'
import ForecastTable from './components/ForecastTable'
import ForecastChart from './components/ForecastChart'
import ForecastChatbot from './components/ForecastChatbot'

import useForecast from './hooks/useForecast'
import useForecastChat from './hooks/useForecastChat'

import { getApiErrorMessage } from '../../api/apiError'

import classes from './DemandForecastingPage.module.css'

// Desktop AI Assistant sidebar sizing. 360px is the fixed width the
// panel already had, so it doubles as the minimum the user can drag
// back to; the maximum is half the viewport, which keeps the forecast
// table and chart beside it readable.
const CHAT_MIN_WIDTH = 360

const getChatMaxWidth = () =>
  Math.max(0, Math.floor(window.innerWidth / 2))

// Below 720px the 50% ceiling is narrower than the panel's own
// minimum. The desktop panel is hidden there (<=768px media query),
// so the floor yields to the viewport instead of overflowing it.
const clampChatWidth = (width: number) => {
  const max = getChatMaxWidth()
  const min = Math.min(CHAT_MIN_WIDTH, max)

  return Math.min(Math.max(width, min), max)
}

const DemandForecastingPage = () => {

  const [chatOpened, setChatOpened] = useState(false)

  const [chatWidth, setChatWidth] = useState(CHAT_MIN_WIDTH)
  const [isResizingChat, setIsResizingChat] = useState(false)

  const chatDrag = useRef<{
    startX: number
    startWidth: number
  } | null>(null)

  const {
    forecastItems,
    hasSalesHistory,
    isLoading,
    isError,
    runForecast,
    isGenerating,
    generateError,

    products,
    selectedProductId,
    setSelectedProductId,
    chartData,
    isChartLoading,
    isChartError,
  } = useForecast()

  const {
    messages: chatMessages,
    sendMessage,
    isSending: isChatSending,
    sendError: chatSendError,
  } = useForecastChat()

  const handleRunForecast = () => {
    void runForecast()
  }

  // The drag is tracked on window so resizing keeps following the
  // pointer past the edge of the panel; both listeners are removed
  // when the drag ends or the page unmounts.
  useEffect(() => {
    if (!isResizingChat) return undefined

    const handleMouseMove = (event: MouseEvent) => {
      const drag = chatDrag.current

      if (!drag) return

      // The panel is anchored to the right edge, so moving the pointer
      // left (a smaller clientX) widens it.
      setChatWidth(
        clampChatWidth(
          drag.startWidth + (drag.startX - event.clientX),
        ),
      )
    }

    const handleMouseUp = () => {
      chatDrag.current = null
      setIsResizingChat(false)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizingChat])

  // Shrinking the window must never leave the panel wider than half of
  // it - the same clamp also runs once on mount.
  useEffect(() => {
    const handleWindowResize = () => {
      setChatWidth((current) => clampChatWidth(current))
    }

    handleWindowResize()
    window.addEventListener('resize', handleWindowResize)

    return () => {
      window.removeEventListener('resize', handleWindowResize)
    }
  }, [])

  const handleChatResizeStart = (
    event: ReactMouseEvent<HTMLDivElement>,
  ) => {
    event.preventDefault()

    chatDrag.current = {
      startX: event.clientX,
      startWidth: chatWidth,
    }
    setIsResizingChat(true)
  }

  return (
    <Box
      className={`${classes.page} ${
        chatOpened ? classes.pageSidebarOpen : ''
      } ${isResizingChat ? classes.pageResizingChat : ''}`}
      style={
        {
          '--chat-width': `${chatWidth}px`,
        } as CSSProperties
      }
    >
      <PageHeader
        title="Demand Forecasting (AI Chatbot)"
        subtitle="AI Assisted demand predictions from historical and sales record"
      />

      <ForecastToolbar
        onRunForecast={handleRunForecast}
        loading={isGenerating}
      />

      {generateError && (
        <Alert
          color="red"
          icon={<AlertCircle size={18} />}
          mb="md"
        >
          {getApiErrorMessage(
            generateError,
            'Unable to generate a forecast. Please try again.',
          )}
        </Alert>
      )}

      {/* All-zero rows are the backend's normal NO_DATA result when no
          sales have ever been recorded for any active product - not a
          failed apply. Spell out the workflow instead of leaving the
          table looking inexplicably empty. */}
      {!isLoading &&
        !isError &&
        forecastItems.length > 0 &&
        !hasSalesHistory && (
          <Alert
            color="blue"
            icon={<Info size={18} />}
            title="No sales history yet"
            mb="md"
          >
            Demand forecasting is calculated from the sales
            transactions you record - it does not read applied
            production plans. Record the units you sold in{' '}
            <Anchor
              component={Link}
              to="/history"
              inherit
            >
              Transaction History
            </Anchor>
            , then select <strong>Run Demand Forecast</strong> to
            recalculate. Applying an optimal plan only saves production
            allocations and resource utilization, so this page keeps
            showing zeros until at least one sales transaction exists.
          </Alert>
        )}

      <Box
        mt="md"
        className={classes.content}
      >
        {/* TABLE */}
        <Box className={classes.table}>
          <ChartCard
            title="Forecast Table"
            subtitle={`${forecastItems.length} products forecasted`}
          >
            <ForecastTable
              forecastItems={forecastItems}
              isLoading={isLoading}
              isError={isError}
            />
          </ChartCard>
        </Box>

        {/* CHATBOT */}
        <Box
          className={`${classes.chat} ${
            chatOpened ? classes.chatOpen : ''
          }`}
        >
          {chatOpened && (
            <Box
              className={classes.chatResizeHandle}
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize AI Assistant"
              aria-valuemin={Math.min(
                CHAT_MIN_WIDTH,
                getChatMaxWidth(),
              )}
              aria-valuemax={getChatMaxWidth()}
              aria-valuenow={chatWidth}
              onMouseDown={handleChatResizeStart}
            />
          )}

          {chatOpened && (
            <Box className={classes.chatWrapper}>
              <ActionIcon
                className={classes.chatCloseButton}
                size={32}
                variant="subtle"
                onClick={() => setChatOpened(false)}
                aria-label="Close AI Assistant"
              >
                <X size={20} />
              </ActionIcon>

              <ForecastChatbot
                messages={chatMessages}
                onSend={sendMessage}
                isSending={isChatSending}
                sendError={chatSendError}
              />
            </Box>
          )}
        </Box>

        {/* DESKTOP CHAT BUTTON */}
        {!chatOpened && (
          <ActionIcon
            className={classes.desktopChatButton}
            size={52}
            radius="xl"
            onClick={() => setChatOpened(true)}
            aria-label="Open AI Assistant"
          >
            <Bot size={24} />
          </ActionIcon>
        )}

        <Box className={classes.mobileChat}>
          {chatOpened && (
            <Box
              className={classes.mobileChatBackdrop}
              onClick={() => setChatOpened(false)}
            />
          )}

          {chatOpened && (
            <Box className={classes.mobileChatPanel}>
              <ForecastChatbot
                messages={chatMessages}
                onSend={sendMessage}
                isSending={isChatSending}
                sendError={chatSendError}
              />
            </Box>
          )}

          <ActionIcon
            className={classes.mobileChatButton}
            size={52}
            radius="xl"
            onClick={() =>
              setChatOpened((prev) => !prev)
            }
            aria-label={
              chatOpened
                ? 'Close AI Assistant'
                : 'Open AI Assistant'
            }
          >
            {chatOpened ? (
              <X size={24} />
            ) : (
              <Bot size={24} />
            )}
          </ActionIcon>
        </Box>

        {/* CHART */}
        <Box className={classes.chart}>
          <ChartCard
            title="Demand Forecast Graph"
            subtitle="Historical and forecasted demand"
            rightSection={
              <Group gap="xs" wrap="nowrap">
                <Text size="sm" c="dimmed">
                  Product:
                </Text>

                <Select
                  placeholder="Select a product"
                  data={products}
                  value={
                    selectedProductId !== null
                      ? String(selectedProductId)
                      : null
                  }
                  onChange={(value) =>
                    setSelectedProductId(
                      value ? Number(value) : null,
                    )
                  }
                  disabled={products.length === 0}
                  w={200}
                  searchable
                />
              </Group>
            }
          >
            <ForecastChart
              data={chartData}
              isLoading={isChartLoading}
              isError={isChartError}
              hasProducts={products.length > 0}
            />
          </ChartCard>
        </Box>
      </Box>
    </Box>
  )
}

export default DemandForecastingPage