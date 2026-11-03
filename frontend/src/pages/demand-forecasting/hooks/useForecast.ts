import { useState } from 'react'

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  fetchForecast,
  fetchForecastTimeseries,
  generateForecast,
} from '../api/forecastApi'

import {
  toForecastProductOptions,
  toUiForecastChartData,
  toUiForecastItems,
  toUiForecastTableItems,
} from '../api/forecastAdapter'

const FORECAST_QUERY_KEY = ['forecast']

// The AI Assistant now has its own hook (useForecastChat.ts) - it's
// an independent concern from the table/chart/generate flow here, so
// it isn't threaded through this hook.
const useForecast = () => {
  const queryClient = useQueryClient()

  const forecastQuery = useQuery({
    queryKey: FORECAST_QUERY_KEY,
    queryFn: fetchForecast,
  })

  const generateMutation = useMutation({
    mutationFn: generateForecast,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: FORECAST_QUERY_KEY,
      })

      // Timeseries recomputes from the same live sales-transaction
      // state as GET /api/forecast (see forecastApi.ts) rather than
      // reading the persisted run, so its values wouldn't actually
      // change here today - invalidated anyway for correctness/
      // freshness rather than assuming that stays true.
      queryClient.invalidateQueries({
        queryKey: ['forecast-timeseries'],
      })
    },
  })

  // --- Chart product selection --------------------------------------
  //
  // Sourced from the already-fetched forecast product list (no
  // separate /api/products call). `requestedProductId` only ever
  // changes on explicit user selection; the "valid" id actually used
  // by the query/chart is derived fresh each render from the current
  // product list - computed during render rather than synced via an
  // effect, so there's never a stale-id render.

  const forecastItems = toUiForecastItems(forecastQuery.data)
  const products = toForecastProductOptions(forecastQuery.data)

  // Authoritative "any recorded sales at all" signal for the page's
  // empty-state guidance. forecast_status is NO_DATA only when a
  // product has zero qualifying sales months (see
  // app/services/forecasting.py::determine_forecast_status), so this
  // doesn't mistake a product whose latest month happened to net 0
  // units for one that has never sold.
  const hasSalesHistory = forecastItems.some(
    (item) => item.status !== 'NO_DATA',
  )

  const [requestedProductId, setSelectedProductId] = useState<
    number | null
  >(null)

  const requestedIsValid = products.some(
    (product) => Number(product.value) === requestedProductId,
  )

  // Default selection prefers the first product (in the backend's own
  // response order - forecastItems mirrors GET /api/forecast's array
  // order exactly) with historical_sales > 0, so the chart doesn't
  // open on a product whose only point is a flat 0-unit forecast when
  // a more informative product is available. "Has history" comes
  // straight from the already-fetched historicalSales field - no
  // extra request, no inference from name/id/confidence/status. Falls
  // back to the first available product exactly as before when no
  // product has any historical demand.
  const defaultProductId =
    forecastItems.find((item) => item.historicalSales > 0)
      ?.id ??
    (products.length > 0 ? Number(products[0].value) : null)

  const selectedProductId = requestedIsValid
    ? requestedProductId
    : defaultProductId

  // Unfiltered - every active product's weekly series at once, in one
  // request. This is the Forecast Table's source (one row per
  // product, built below) and the Forecast Chart's source (the
  // selected product's own series, picked out of this same response
  // rather than fetched again) - the two never disagree on weekly
  // totals because neither recomputes it independently.
  const timeseriesQuery = useQuery({
    queryKey: ['forecast-timeseries'],
    queryFn: () => fetchForecastTimeseries(),
  })

  const selectedProductSeries = timeseriesQuery.data?.products.find(
    (product) => product.product_id === selectedProductId,
  )

  return {
    forecastItems,
    hasSalesHistory,
    isLoading: forecastQuery.isLoading,
    isError: forecastQuery.isError,

    runForecast: generateMutation.mutateAsync,
    isGenerating: generateMutation.isPending,
    generateError: generateMutation.error,

    products,
    selectedProductId,
    setSelectedProductId,

    chartData: toUiForecastChartData(
      selectedProductSeries?.series ?? [],
    ),
    // One row per product (the original table shape) - every
    // product's own latest historical week and first forecast week,
    // never split across multiple rows.
    forecastTableItems: toUiForecastTableItems(timeseriesQuery.data),
    isChartLoading: forecastQuery.isLoading || timeseriesQuery.isLoading,
    isChartError: timeseriesQuery.isError,
  }
}

export default useForecast
