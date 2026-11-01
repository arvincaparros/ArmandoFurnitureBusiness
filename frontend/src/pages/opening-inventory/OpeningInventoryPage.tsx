import { useState } from 'react'

import {
  Alert,
  Button,
  Card,
  Group,
  Loader,
  Stack,
  Title,
} from '@mantine/core'

import { AlertTriangle, ShieldCheck } from 'lucide-react'

import PageHeader from '../../components/common/PageHeader'
import AppTable from '../../components/tables/AppTable'

import OpeningInventoryForm from './components/OpeningInventoryForm'
import ReviewConfirmModal from './components/ReviewConfirmModal'
import useOpeningInventory from './hooks/useOpeningInventory'

import type { Column } from '../../components/tables/AppTable'
import type { OpeningInventorySetResponse } from './api/openingInventoryTypes'

const historyColumns: Column<OpeningInventorySetResponse>[] = [
  { accessor: 'set_number', title: 'Set' },
  { accessor: 'status', title: 'Status' },
  {
    accessor: 'effective_date',
    title: 'Effective date',
    render: (row) => row.effective_date.slice(0, 10),
  },
  {
    accessor: 'reviewed_at',
    title: 'Reviewed at',
    render: (row) =>
      row.reviewed_at ? row.reviewed_at.slice(0, 10) : '—',
  },
  {
    accessor: 'reviewed_by_username',
    title: 'Reviewed by',
    render: (row) => row.reviewed_by_username ?? '—',
  },
]

const OpeningInventoryPage = () => {
  const {
    sets,
    draftSet,
    reviewedSet,
    isStockValidationEnabled,
    products,
    isLoading,
    isError,
    createDraft,
    updateDraft,
    isSaving,
    reviewSet,
  } = useOpeningInventory()

  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false)

  const handleSave = (
    effectiveDate: string,
    notes: string | null,
    items: { product_id: number; quantity: number }[],
  ) =>
    draftSet
      ? updateDraft({
        id: draftSet.id,
        data: { effective_date: effectiveDate, notes, items },
      })
      : createDraft({
        effective_date: effectiveDate,
        notes,
        items,
      })

  return (
    <Stack gap="md">
      <PageHeader
        title="Opening Stock"
        subtitle="Declare the finished goods you physically hold, then mark the set as reviewed."
      />

      {isStockValidationEnabled ? (
        <Alert
          color="green"
          variant="light"
          icon={<ShieldCheck size={18} />}
        >
          Stock-based validation is active. Sales are checked
          against available stock, and {reviewedSet?.set_number} is
          the opening balance every stock figure starts from.
        </Alert>
      ) : (
        // Copy corrected against the shipped behaviour (Task 23 /
        // Amendment A): a sale is REFUSED with 409 until a complete
        // reviewed set exists. The plan's original wording here said
        // "sales are recorded without being checked against stock",
        // which described the soft gate that was rejected - telling
        // the user their sales are being recorded when the API
        // refuses them would be worse than saying nothing.
        <Alert
          color="orange"
          variant="light"
          icon={<AlertTriangle size={18} />}
        >
          Sales cannot be recorded yet. Declare the units you
          physically hold for every product — including zero — and
          mark the set as reviewed. Until then new sales are
          refused, because there is no confirmed opening balance to
          check them against.
        </Alert>
      )}

      {isError && (
        <Alert
          color="red"
          icon={<AlertTriangle size={18} />}
        >
          Unable to load opening inventory right now.
        </Alert>
      )}

      {isLoading && <Loader size="sm" />}

      {!isLoading && !isError && !reviewedSet && (
        <Card withBorder radius="lg" shadow="sm" p="lg">
          <Title order={4} mb="md">
            Declare opening balances
          </Title>

          <OpeningInventoryForm
            products={products}
            draftSet={draftSet}
            isSaving={isSaving}
            onSave={handleSave}
          />

          <Group justify="flex-end" mt="md">
            <Button
              onClick={() => setIsReviewModalOpen(true)}
              disabled={
                !draftSet || draftSet.items.length === 0
              }
            >
              Mark as reviewed
            </Button>
          </Group>
        </Card>
      )}

      <Card withBorder radius="lg" shadow="sm" p="lg">
        <Title order={4} mb="md">
          Declaration history
        </Title>

        <AppTable
          columns={historyColumns}
          data={sets}
          emptyMessage="No opening inventory has been declared yet."
        />
      </Card>

      <ReviewConfirmModal
        opened={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        onConfirm={() => reviewSet(draftSet!.id)}
      />
    </Stack>
  )
}

export default OpeningInventoryPage
