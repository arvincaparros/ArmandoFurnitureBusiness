import { useState } from 'react'

import { ActionIcon, Alert, Box, Group, Select, Text } from '@mantine/core'
import { AlertCircle, Bot, X } from 'lucide-react'

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

const DemandForecastingPage = () => {

  const [chatOpened, setChatOpened] = useState(false)

  const {
    forecastItems,
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

  return (
    <Box
      className={`${classes.page} ${
        chatOpened ? classes.pageSidebarOpen : ''
      }`}
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