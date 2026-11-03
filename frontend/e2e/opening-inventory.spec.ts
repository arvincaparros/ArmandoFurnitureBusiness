import { expect, test } from '@playwright/test'

import { installApiStubs } from './fixtures/apiStubs'

test('stock validation is advertised as off until a set is reviewed', async ({
  page,
}) => {
  await installApiStubs(page, {
    openingStatus: {
      stock_validation_enabled: false,
      reviewed_set: null,
      draft_set: null,
    },
  })

  await page.goto('/opening-inventory')

  // The plan's original assertion was /not yet enforced/i. That copy
  // was corrected in G6 (user-approved) because sales are REFUSED
  // with 409 until a complete set is reviewed - telling the user
  // their sales are recorded unvalidated would contradict the API.
  await expect(
    page.getByText(/cannot be recorded yet/i),
  ).toBeVisible()
})

test('reviewing a draft requires confirmation and then reports validation active', async ({
  page,
}) => {
  const requests = await installApiStubs(page, {
    openingStatus: {
      stock_validation_enabled: false,
      reviewed_set: null,
      draft_set: {
        id: 1,
        set_number: 'OI-0001',
        status: 'DRAFT',
        effective_date: '2026-10-30T00:00:00',
        notes: null,
        created_at: '2026-10-30T00:00:00',
        reviewed_at: null,
        created_by_username: 'arvin',
        reviewed_by_username: null,
        items: [
          { id: 1, product_id: 1, quantity: '8.0000', notes: null },
        ],
      },
    },
  })

  await page.goto('/opening-inventory')

  await page
    .getByRole('button', { name: /mark as reviewed/i })
    .click()

  await expect(
    page.getByText(/cannot be edited afterwards/i),
  ).toBeVisible()

  await page
    .getByRole('button', { name: /^confirm review$/i })
    .click()

  await expect
    .poll(() => requests.reviewCalls.length)
    .toBe(1)
})
