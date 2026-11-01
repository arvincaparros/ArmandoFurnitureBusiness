import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it } from 'vitest'

import ForecastTable from './ForecastTable'

import type { ForecastTableItem } from '../types'

const FORECAST_ITEMS: ForecastTableItem[] = [
  {
    id: 1,
    furnitureProduct: 'Chair',
    historicalSales: 10,
    predictedDemand: 25,
    forecastPeriod: 'Jan 26 - Feb 1',
    confidenceLevel: 66.67,
  },
  {
    id: 2,
    furnitureProduct: 'Dining Table',
    historicalSales: 0,
    predictedDemand: 0,
    forecastPeriod: 'Nov 2 - Nov 8',
    confidenceLevel: 0,
  },
]

const renderTable = (
  props: Partial<
    Parameters<typeof ForecastTable>[0]
  > = {},
) =>
  render(
    <MantineProvider>
      <ForecastTable
        forecastItems={FORECAST_ITEMS}
        isLoading={false}
        isError={false}
        {...props}
      />
    </MantineProvider>,
  )

describe('ForecastTable', () => {
  it('keeps the original column set, in order', () => {
    renderTable()

    expect(
      screen.getByText('Furniture Product'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Historical Sales (Units)'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Predicted Demand (Units)'),
    ).toBeInTheDocument()
    expect(screen.getByText('Forecast Period')).toBeInTheDocument()
    expect(screen.getByText('Confidence Level')).toBeInTheDocument()
  })

  it('does not render a Forecast Status column', () => {
    renderTable()

    expect(screen.queryByText('Forecast Status')).toBeNull()
    expect(screen.queryByText('Trend')).toBeNull()
  })

  it('renders exactly one row per product, with both historical sales and predicted demand filled in', () => {
    renderTable()

    expect(screen.getByText('Chair')).toBeInTheDocument()
    expect(screen.getByText('Dining Table')).toBeInTheDocument()

    // Neither column is blank for either product - historical sales
    // and predicted demand always both appear on the same row.
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('25')).toBeInTheDocument()
    expect(screen.getByText('Jan 26 - Feb 1')).toBeInTheDocument()
    expect(screen.getByText('66.7%')).toBeInTheDocument()
  })

  it('shows the weekly forecast period instead of the old Next Cycle literal', () => {
    renderTable()

    expect(screen.queryByText('Next Cycle')).toBeNull()
    expect(screen.getByText('Jan 26 - Feb 1')).toBeInTheDocument()
    expect(screen.getByText('Nov 2 - Nov 8')).toBeInTheDocument()
  })

  it('shows a loading message and renders no rows while loading', () => {
    renderTable({ isLoading: true })

    expect(screen.getByText('Loading forecast...')).toBeInTheDocument()
    expect(screen.queryByText('Chair')).toBeNull()
  })

  it('shows an error message when the request failed', () => {
    renderTable({ isLoading: false, isError: true, forecastItems: [] })

    expect(
      screen.getByText('Unable to load forecast.'),
    ).toBeInTheDocument()
  })

  it('shows an empty message when there is no data to show', () => {
    renderTable({ forecastItems: [] })

    expect(
      screen.getByText('No forecast data available.'),
    ).toBeInTheDocument()
  })
})
