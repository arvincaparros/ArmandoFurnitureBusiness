import { expect, test } from '@playwright/test'

import { installApiStubs } from './fixtures/apiStubs'

// The ledger row that marks the latest OPTIMAL run (id 7, see
// fixtures/apiStubs.ts) as already applied.
const APPLIED_LEDGER_ROW = {
  id: 1,
  application_number: 'PA-0001',
  production_cycle_id: 3,
  optimization_run_id: 7,
  applied_at: '2026-10-30T09:00:02',
  product_items: [{ product_id: 1, quantity_produced: '10.0000' }],
  resource_items: [],
}

const openAddTransaction = async (
  page: import('@playwright/test').Page,
) => {
  await page.goto('/history')

  await page
    .getByRole('button', { name: /add transaction/i })
    .first()
    .click()

  // The product picker is a Mantine Select, which exposes role
  // combobox - not textbox like the numeric inputs below it.
  await page
    .getByRole('combobox', { name: /furniture product/i })
    .click()

  await page
    .getByRole('option', { name: 'Ordinary Table' })
    .click()
}

test('the Apply modal says it ADDS units to the cycle', async ({
  page,
}) => {
  await installApiStubs(page)

  await page.goto('/production')

  await page
    .getByRole('button', { name: /apply to production/i })
    .click()

  await expect(
    page.getByText(/add \d+ units to this cycle/i),
  ).toBeVisible()

  await expect(
    page.getByText(/replace the current committed/i),
  ).toHaveCount(0)
})

test('an already-applied plan blocks Apply and explains why', async ({
  page,
}) => {
  await installApiStubs(page, {
    applications: [APPLIED_LEDGER_ROW],
  })

  await page.goto('/production')

  await expect(
    page.getByText(/already been applied/i),
  ).toBeVisible()

  await expect(
    page.getByRole('button', { name: /apply to production/i }),
  ).toBeDisabled()
})

test('Quantity Produced is read-only, auto-filled, and never sent', async ({
  page,
}) => {
  const requests = await installApiStubs(page)

  await openAddTransaction(page)

  const produced = page.getByRole('textbox', {
    name: /quantity produced/i,
  })

  await expect(produced).toHaveAttribute('readonly', '')

  // cycle_produced from the stubbed /api/inventory, not
  // available_stock - the produced figure must never be stock.
  await expect(produced).toHaveValue('20')

  await page
    .getByRole('textbox', { name: /quantity sold/i })
    .fill('1')

  await page.getByRole('button', { name: /^save$/i }).click()

  await expect
    .poll(() => requests.transactionCalls.length)
    .toBe(1)

  expect(requests.transactionCalls[0]).not.toHaveProperty(
    'quantity_produced',
  )
})

test('an oversell is blocked client-side and never submitted', async ({
  page,
}) => {
  const requests = await installApiStubs(page)

  await openAddTransaction(page)

  await page
    .getByRole('textbox', { name: /quantity sold/i })
    .fill('16')

  await expect(
    page.getByText(/only 15 units are available/i),
  ).toBeVisible()

  await expect(
    page.getByRole('button', { name: /^save$/i }),
  ).toBeDisabled()

  expect(requests.transactionCalls).toHaveLength(0)
})

test('the three inventory figures are labelled separately', async ({
  page,
}) => {
  await installApiStubs(page)

  await page.goto('/inventory')

  await expect(
    page.getByRole('columnheader', { name: /produced this cycle/i }),
  ).toBeVisible()

  await expect(
    page.getByRole('columnheader', { name: /sold this cycle/i }),
  ).toBeVisible()

  await expect(
    page.getByRole('columnheader', { name: /available stock/i }),
  ).toBeVisible()

  await expect(
    page.getByText(/across all cycles/i),
  ).toBeVisible()
})
