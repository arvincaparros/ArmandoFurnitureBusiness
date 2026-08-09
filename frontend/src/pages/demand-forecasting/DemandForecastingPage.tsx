import { useState } from 'react'

import { ActionIcon, Box } from '@mantine/core'
import { Bot, X } from 'lucide-react'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import ForecastToolbar from './components/ForecastToolbar'
import ForecastTable from './components/ForecastTable'
import ForecastChart from './components/ForecastChart'
import ForecastChatbot from './components/ForecastChatbot'

import useForecast from './hooks/useForecast'

import classes from './DemandForecastingPage.module.css'

const DemandForecastingPage = () => {

  const [chatOpened, setChatOpened] = useState(false)

  const {
    forecastItems,
    forecastChartData,
    chatMessages,
    runForecast,
  } = useForecast()

  const handleRunOptimization = () => {
    runForecast()
  }

  return (
    <Box className={classes.page}>
      <PageHeader
        title="Demand Forecasting (AI Chatbot)"
        subtitle="AI Assisted demand predictions from historical and sales record"
      />

      <ForecastToolbar
        onRunOptimization={
          handleRunOptimization
        }
      />

      <Box
        mt="md"
        className={classes.content}
      >
        {/* TABLE */}
        <Box className={classes.table}>
          <ChartCard
            title="Demand Forecast"
            subtitle={`${forecastItems.length} products forecasted`}
          >
            <ForecastTable
              forecastItems={forecastItems}
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
          >
            <ForecastChart
              data={forecastChartData}
            />
          </ChartCard>
        </Box>
      </Box>
    </Box>
  )
}

export default DemandForecastingPage