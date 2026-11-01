import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { describe, expect, it } from 'vitest'

import ForecastTable from './ForecastTable'

import type { ForecastWeekRow } from '../types'

const WEEK_ROWS: ForecastWeekRow[] = [
  {
    furnitureProduct: 'Chair',
    weekLabel: 'Jan 5 - Jan 11',
    historicalSales: 10,
  },
  {
    furnitureProduct: 'Chair',
    weekLabel: 'Jan 26 - Feb 1',
    predictedDemand: 25,
    confidenceLevel: 66.67,
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
        weekRows={WEEK_ROWS}
        isLoading={false}
        isError={false}
        {...props}
      />
    </MantineProvider>,
  )

describe('ForecastTable', () => {
  it('keeps the original column set, in order, with Forecast Period in place of Next Cycle', () => {
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

  it('does not render a Trend or Forecast Status column', () => {
    renderTable()

    expect(screen.queryByText('Trend')).toBeNull()
    expect(screen.queryByText('Forecast Status')).toBeNull()
  })

  it('renders each weekly row with its own forecast period label', () => {
    renderTable()

    expect(screen.getByText('Jan 5 - Jan 11')).toBeInTheDocument()
    expect(screen.getByText('Jan 26 - Feb 1')).toBeInTheDocument()
  })

  it('keeps historical sales and predicted demand in separate columns, never combined', () => {
    renderTable()

    // The historical row has a value in Historical Sales and a
    // placeholder in Predicted Demand; the forecast row is the
    // reverse - never both populated on one row, and never merged
    // into one "quantity" value.
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('25')).toBeInTheDocument()
  })

  it('shows confidence level only on the forecast row', () => {
    renderTable()

    expect(screen.getByText('66.7%')).toBeInTheDocument()

    // The historical row's Predicted Demand and Confidence Level
    // cells, plus the forecast row's Historical Sales cell, all show
    // the placeholder rather than a stale or inherited value.
    expect(screen.getAllByText('—')).toHaveLength(3)
  })

  it('shows a loading message and renders no rows while loading', () => {
    renderTable({ isLoading: true })

    expect(screen.getByText('Loading forecast...')).toBeInTheDocument()
    expect(screen.queryByText('Jan 5 - Jan 11')).toBeNull()
  })

  it('shows an error message when the request failed', () => {
    renderTable({ isLoading: false, isError: true, weekRows: [] })

    expect(
      screen.getByText('Unable to load forecast.'),
    ).toBeInTheDocument()
  })

  it('shows an empty message when there is no data to show', () => {
    renderTable({ weekRows: [] })

    expect(
      screen.getByText('No forecast data available for this product.'),
    ).toBeInTheDocument()
  })
})
