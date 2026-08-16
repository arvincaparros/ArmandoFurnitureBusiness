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
      // freshness rather than assuming that stays true. Prefix match
      // (no productId) so this covers whichever product is selected.
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

  const timeseriesQuery = useQuery({
    queryKey: ['forecast-timeseries', selectedProductId],
    queryFn: () => fetchForecastTimeseries(selectedProductId as number),
    enabled: selectedProductId !== null,
  })

  return {
    forecastItems,
    isLoading: forecastQuery.isLoading,
    isError: forecastQuery.isError,

    runForecast: generateMutation.mutateAsync,
    isGenerating: generateMutation.isPending,
    generateError: generateMutation.error,

    products,
    selectedProductId,
    setSelectedProductId,

    chartData: toUiForecastChartData(timeseriesQuery.data),
    // Bridges the two-phase load (resolve the product list, then that
    // product's series) - selectedProductId is derived synchronously
    // from `products` above, so as soon as products are known and
    // non-empty there's always a valid id and timeseriesQuery.isLoading
    // alone reflects whether the chart should still be waiting.
    isChartLoading:
      forecastQuery.isLoading ||
      (products.length > 0 && timeseriesQuery.isLoading),
    isChartError: timeseriesQuery.isError,
  }
}

export default useForecast
