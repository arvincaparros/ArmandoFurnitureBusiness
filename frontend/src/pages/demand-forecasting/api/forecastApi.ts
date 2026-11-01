import apiClient from '../../../api/client'

import type {
  ForecastChatResponse,
  ForecastResponse,
  ForecastTimeSeriesResponse,
} from './forecastTypes'

export async function fetchForecast(): Promise<ForecastResponse> {
  const response = await apiClient.get<ForecastResponse>(
    '/api/forecast',
  )

  return response.data
}

// The backend both computes and persists this run (writes to
// forecast_runs/forecast_results - app/services/forecasting.py::
// generate_forecast) - the frontend only triggers it and refetches
// GET /api/forecast afterward, it never persists anything itself.
export async function generateForecast(): Promise<ForecastResponse> {
  const response = await apiClient.post<ForecastResponse>(
    '/api/forecast/generate',
  )

  return response.data
}

// Omit productId to fetch every active product's series at once (the
// Forecast Table's source - one row per product) and pass it to scope
// to a single product (the Forecast Chart's source). 404s if
// productId doesn't match an active product - left to the caller.
export async function fetchForecastTimeseries(
  productId?: number,
): Promise<ForecastTimeSeriesResponse> {
  const response = await apiClient.get<ForecastTimeSeriesResponse>(
    '/api/forecast/timeseries',
    {
      params:
        productId === undefined ? {} : { product_id: productId },
    },
  )

  return response.data
}

// The backend builds its own forecast-data context server-side and
// calls Gemini - this only ever sends the user's raw message, never
// any client-computed forecast values.
export async function sendForecastChatMessage(
  message: string,
): Promise<ForecastChatResponse> {
  const response = await apiClient.post<ForecastChatResponse>(
    '/api/forecast/chat',
    { message },
  )

  return response.data
}
