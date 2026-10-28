import { Center, Loader, Paper, Text, useMantineTheme } from '@mantine/core'
import { LineChart } from '@mantine/charts'

import type { ForecastChartData } from '../types'

interface ForecastChartProps {
  data: ForecastChartData[]
  isLoading: boolean
  isError: boolean
  hasProducts: boolean
}

const HISTORICAL_SERIES = 'historicalDemand'
const FORECAST_SERIES = 'forecastedDemand'

// Shape recharts hands to a series' `dot` renderer.
interface ChartDotProps {
  cx?: number
  cy?: number
  index?: number
}

// Shape recharts hands to a custom tooltip `content` renderer. Its
// payload is readonly recharts data; only the hovered row is used.
interface ChartTooltipProps {
  payload?: readonly { payload?: ForecastChartData }[]
}

// Recharts renders whatever this returns for every point it asks
// about, so every point except the forecast end returns an empty
// group: the last transaction anchors the dashed forecast segment but
// must keep looking like a plain historical dot.
const renderForecastDot = (
  { cx, cy, index }: ChartDotProps,
  lastIndex: number,
  fill: string,
) => {
  if (index !== lastIndex || cx === undefined || cy === undefined) {
    return <g />
  }

  return (
    <circle
      cx={cx}
      cy={cy}
      r={4}
      fill={fill}
      stroke={fill}
      strokeWidth={1}
    />
  )
}

// Reads the hovered ROW rather than per-series values, so the row that
// carries both a sale and the forecast line's starting value is still
// reported as a sale, never as forecast demand.
const ForecastTooltip = ({ payload }: ChartTooltipProps) => {
  const row = payload?.[0]?.payload

  if (!row) {
    return null
  }

  return (
    <Paper px="md" py="sm" withBorder shadow="md" radius="md">
      <Text fw={600} size="sm">
        {row.date}
      </Text>

      {row.isForecast ? (
        <Text size="xs" c="dimmed">
          Forecasted demand: {row.forecastedDemand ?? 0} units
        </Text>
      ) : (
        <>
          <Text size="xs" c="dimmed">
            Quantity sold: {row.historicalDemand ?? 0} units
          </Text>
          {row.quantityProduced !== undefined && (
            <Text size="xs" c="dimmed">
              Quantity produced: {row.quantityProduced} units
            </Text>
          )}
          {row.transactionNumber && (
            <Text size="xs" c="dimmed">
              {row.transactionNumber}
            </Text>
          )}
        </>
      )}
    </Paper>
  )
}

const ForecastChart = ({
  data,
  isLoading,
  isError,
  hasProducts,
}: ForecastChartProps) => {
  const theme = useMantineTheme()

  if (isLoading) {
    return (
      <Center h={280}>
        <Loader />
      </Center>
    )
  }

  if (isError) {
    return (
      <Center h={280}>
        <Text c="dimmed">
          Unable to load forecast timeseries.
        </Text>
      </Center>
    )
  }

  if (!hasProducts) {
    return (
      <Center h={280}>
        <Text c="dimmed">
          No products available.
        </Text>
      </Center>
    )
  }

  if (data.length === 0) {
    return (
      <Center h={280}>
        <Text c="dimmed">
          No forecast timeseries available for this product.
        </Text>
      </Center>
    )
  }

  // A product with no recorded sales still gets exactly one forecast
  // point (a flat 0-unit projection) from GET /api/forecast/timeseries,
  // which otherwise renders as an empty-looking chart. There is no
  // historical demand to plot until sales transactions exist, so say
  // that explicitly rather than drawing a lone zero dot.
  const hasHistoricalPoints = data.some(
    (point) => point.historicalDemand !== undefined,
  )

  if (!hasHistoricalPoints) {
    return (
      <Center h={280}>
        <Text c="dimmed" ta="center">
          No sales history for this product yet. Record sales
          transactions and run the demand forecast to see historical
          and forecasted demand.
        </Text>
      </Center>
    )
  }

  const lastHistoricalIndex = data.reduce(
    (lastIndex, point, index) =>
      point.historicalDemand === undefined ? lastIndex : index,
    -1,
  )

  // The forecast is its own dashed series so it can never be read as a
  // sale, and it starts on the last real transaction: that row carries
  // both its historical value and the forecast line's starting value,
  // which is what makes the dashed segment connect to the history.
  // The row itself is unchanged - it is still one transaction, and the
  // forecast dot is suppressed there.
  const chartData = data.map((point, index) =>
    index === lastHistoricalIndex
      ? { ...point, forecastedDemand: point.historicalDemand }
      : point,
  )

  // The historical line uses the active theme's primary color, so the
  // forecast must not: blue on the wood theme (matching the supplied
  // design), violet on the classic theme where the primary is blue.
  const forecastColor =
    theme.primaryColor === 'blue' ? 'grape.6' : 'blue.6'
  const forecastFill = `var(--mantine-color-${forecastColor.replace(
    '.',
    '-',
  )})`

  return (
    <LineChart
      h={280}
      data={chartData}
      dataKey="date"
      series={[
        {
          name: HISTORICAL_SERIES,
          label: 'Historical Demand (Transaction)',
        },
        {
          name: FORECAST_SERIES,
          label: 'Forecasted Demand',
          color: forecastColor,
          strokeDasharray: '6 6',
        },
      ]}
      curveType="linear"
      withLegend
      withTooltip
      withDots
      tooltipProps={{
        content: ({ payload }) => (
          <ForecastTooltip payload={payload} />
        ),
      }}
      lineProps={(series) =>
        series.name === FORECAST_SERIES
          ? {
              dot: (dotProps: ChartDotProps) =>
                renderForecastDot(
                  dotProps,
                  chartData.length - 1,
                  forecastFill,
                ),
            }
          : {}
      }
      valueFormatter={(value) =>
        `${value} units`
      }
    />
  )
}

export default ForecastChart
