
import {
  chatMessages,
  forecastChartData,
  forecastItems,
} from '../mock/forecastData'

const useForecast = () => {
  const runForecast = () => {
    console.log('Running demand forecast...')
  }

  return {
    forecastItems,
    forecastChartData,
    chatMessages,
    runForecast,
  }
}

export default useForecast