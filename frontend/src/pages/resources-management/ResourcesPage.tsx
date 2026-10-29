import { useState } from 'react'

import { Search } from 'lucide-react'
import { TextInput } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import AddResourceModal from './components/AddResourceModal'
import ResourceTable from './components/ResourceTable'
import ResourceToolbar from './components/ResourceToolbar'
import DeleteResourceModal from './components/DeleteResourceModal'
import ReactivateResourceModal from './components/ReactivateResourceModal'
import PermanentDeleteResourceModal from './components/PermanentDeleteResourceModal'

import type {
  Resource,
  ResourceStatusFilter,
  ResourceSubmission,
} from './types'

import useResources from './hooks/useResources'

import { notify } from '../../utils/notify'

const ResourcesPage = () => {
  const [opened, setOpened] = useState(false)

  const [selectedResource, setSelectedResource] =
  useState<Resource | null>(null)

  const [deleteOpened, setDeleteOpened] = useState(false)

  const [reactivateOpened, setReactivateOpened] =
    useState(false)

  const [permanentDeleteOpened, setPermanentDeleteOpened] =
    useState(false)

  const [statusFilter, setStatusFilter] =
    useState<ResourceStatusFilter>('active')

  const [search, setSearch] = useState('')

  const [sortBy, setSortBy] = useState<keyof Resource>('name')

  const [reverse, setReverse] = useState(false)

  const {
    resources,
    inactiveResources,
    selectableResources,
    isExistingResourcesLoading,
    isExistingResourcesError,
    isLoading,
    isError,
    hasCycle,
    updateResource,
    createResource,
    deleteResource,
    reactivateResource,
    permanentlyDeleteResource,
    savePricing,
  } = useResources()

  // Both slices come from the catalog so the search and sort apply to
  // whichever view is selected - inactive rows are never mixed into
  // the active list.
  const sourceResources =
    statusFilter === 'inactive'
      ? inactiveResources
      : resources

  const filteredResources = sourceResources.filter((resource) =>
    resource.name
      .toLowerCase()
      .includes(search.toLowerCase()),
  )

  const sortedResources = [...filteredResources].sort(
    (a, b) => {
      const aValue = a[sortBy]
      const bValue = b[sortBy]

      // availableQuantity/unitPrice can be null (not yet configured
      // for the current cycle) - same null-guard already used by
      // Product Data Management's sort for its own null cost columns.
      if (aValue === null || bValue === null)
        return 0

      if (aValue < bValue)
        return reverse ? 1 : -1

      if (aValue > bValue)
        return reverse ? -1 : 1

      return 0
    },
  )

  const handleSaveResource = async (
    submission: ResourceSubmission,
  ) => {
    if (submission.kind === 'create') {
      // "Create New" in the Add Resource form: the only path that
      // writes a new master Resource record. The row the server
      // creates keeps its own id, and the optional availability/price
      // below is written against that same id - so a resource is
      // never duplicated, and it shows up in the catalog (and thus in
      // the form's own selection list) immediately.
      const created = await createResource(submission.data)

      if (submission.pricing) {
        await savePricing({
          resourceId: created.id,
          data: submission.pricing,
        })
      }

      notify.added(created.name)

      setSelectedResource(null)
      setOpened(false)

      return
    }

    if (submission.kind === 'inventory') {
      // Add mode assigns an existing catalog resource to the latest
      // production cycle. The only write is CycleResource
      // availability/price (create or update in useResources.ts) -
      // never POST /api/resources, so this form cannot create a
      // duplicate catalog row.
      await savePricing({
        resourceId: submission.resourceId,
        data: submission.pricing,
      })

      const current = resources.find(
        (candidate) =>
          candidate.id === submission.resourceId,
      )

      if (!current || current.availableQuantity === null) {
        notify.added(submission.resourceName)
      } else if (
        current.availableQuantity !==
          submission.pricing.available_quantity ||
        current.unitPrice !== submission.pricing.unit_price
      ) {
        notify.resourceNeedsReoptimization(
          submission.resourceName,
        )
      } else {
        notify.updated(submission.resourceName)
      }

      setSelectedResource(null)
      setOpened(false)

      return
    }

    await updateResource({
      id: submission.resourceId,
      data: submission.data,
    })

    const quantityChanged =
      submission.pricing !== null &&
      submission.pricing.available_quantity !==
        selectedResource?.availableQuantity

    const unitPriceChanged =
      submission.pricing !== null &&
      submission.pricing.unit_price !==
        selectedResource?.unitPrice

    const optimizationRelevantFieldChanged =
      (submission.data.resource_type !== undefined &&
        submission.data.resource_type !==
          selectedResource?.resourceType) ||
      (submission.data.is_active !== undefined &&
        submission.data.is_active !==
          selectedResource?.isActive)

    const notifyAction =
      quantityChanged ||
      unitPriceChanged ||
      optimizationRelevantFieldChanged
        ? () =>
            notify.resourceNeedsReoptimization(
              submission.resourceName,
            )
        : () => notify.updated(submission.resourceName)

    // Availability/price are a second write against CycleResource
    // (see useResources.ts) - only attempted when the modal actually
    // collected them (a production cycle exists), so editing a
    // resource with no cycle yet still succeeds for its global
    // fields. The success notification is deliberately deferred until
    // after this write (or skipped entirely, if there's none) - firing
    // it any earlier would tell the user the save succeeded even if
    // this part then fails.
    if (submission.pricing) {
      await savePricing({
        resourceId: submission.resourceId,
        data: submission.pricing,
      })
    }

    notifyAction()

    setSelectedResource(null)
    setOpened(false)
  }

  const handleEditResource = (
    resource: Resource,
  ) => {
    setSelectedResource(resource)
    setOpened(true)
  }

  const handleDeleteResource = (
    resource: Resource,
  ) => {
    setSelectedResource(resource)
    setDeleteOpened(true)
  }

  const handleReactivateResource = (
    resource: Resource,
  ) => {
    setSelectedResource(resource)
    setReactivateOpened(true)
  }

  const handlePermanentDeleteResource = (
    resource: Resource,
  ) => {
    setSelectedResource(resource)
    setPermanentDeleteOpened(true)
  }

  const handleOpenAdd = () => {
    setSelectedResource(null)
    setOpened(true)
  }

  const handleConfirmDelete = async () => {
    if (!selectedResource) return

    await deleteResource(selectedResource.id)

    notify.deleted(selectedResource.name)

    setDeleteOpened(false)
    setSelectedResource(null)
  }

  // Deliberately does NOT swallow the error: a blocked delete
  // rejects with a 409, and PermanentDeleteResourceModal needs that
  // rejection to surface the backend's specific reason and stay
  // open. The notification and the state resets below therefore only
  // run when the row was really removed. The list itself refreshes
  // through the mutation's own query invalidation (useResources.ts).
  const handleConfirmPermanentDelete = async () => {
    if (!selectedResource) return

    const { name } = selectedResource

    await permanentlyDeleteResource(selectedResource.id)

    notify.permanentlyDeleted(name)

    setPermanentDeleteOpened(false)
    setSelectedResource(null)
  }

  const handleConfirmReactivate = async () => {
    if (!selectedResource) return

    // PATCH is_active on the SAME resource id - no create, no
    // rewrite of category/unit, and no CycleResource write.
    await reactivateResource(selectedResource.id)

    notify.reactivated(selectedResource.name)

    setReactivateOpened(false)
    setSelectedResource(null)
  }

  const handleSort = (
    accessor: keyof Resource | string,
  ) => {
    if (sortBy === accessor) {
      setReverse((prev) => !prev)
    } else {
      setSortBy(accessor as keyof Resource)
      setReverse(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Resources"
        subtitle="Manage raw materials and inventory."
      />

      <ResourceToolbar
        onAdd={handleOpenAdd}
        statusFilter={statusFilter}
        onStatusFilterChange={(value) => {
          setStatusFilter(value)
          setSearch('')
        }}
        activeCount={resources.length}
        inactiveCount={inactiveResources.length}
      />

      <ChartCard
        title={
          statusFilter === 'inactive'
            ? 'Inactive Resources'
            : 'Resources'
        }
        subtitle={
          statusFilter === 'inactive'
            ? `Not available for new products or production cycles • ${filteredResources.length} resource${filteredResources.length !== 1 ? 's' : ''}`
            : `Current inventory list • ${filteredResources.length} resource${filteredResources.length !== 1 ? 's' : ''}`
        }
        rightSection={
          <TextInput
            placeholder="Search resources..."
            value={search}
            onChange={(e) =>
              setSearch(e.currentTarget.value)
            }
            leftSection={<Search size={16} />}
            w={260}
          />
        }

      >
        <ResourceTable
          resources={sortedResources}
          onEdit={handleEditResource}
          onDelete={handleDeleteResource}
          onReactivate={handleReactivateResource}
          onPermanentDelete={handlePermanentDeleteResource}
          isLoading={
            statusFilter === 'inactive'
              ? isExistingResourcesLoading || isLoading
              : isLoading
          }
          isError={
            statusFilter === 'inactive'
              ? isExistingResourcesError || isError
              : isError
          }
          emptyMessage={
            statusFilter === 'inactive'
              ? 'No inactive resources.'
              : 'No resources found.'
          }
          sortBy={sortBy}
          reverse={reverse}
          onSort={handleSort}
        />
      </ChartCard>

      <AddResourceModal
        opened={opened}
        resource={selectedResource}
        selectableResources={selectableResources}
        isExistingResourcesLoading={
          isExistingResourcesLoading || isLoading
        }
        isExistingResourcesError={isExistingResourcesError}
        hasCycle={hasCycle}
        onClose={() => {
          setSelectedResource(null)
          setOpened(false)
        }}
        onSave={handleSaveResource}
      />

      <DeleteResourceModal
        opened={deleteOpened}
        resource={selectedResource}
        onClose={() => {
          setDeleteOpened(false)
          setSelectedResource(null)
        }}
        onConfirm={handleConfirmDelete}
      />

      <ReactivateResourceModal
        opened={reactivateOpened}
        resource={selectedResource}
        onClose={() => {
          setReactivateOpened(false)
          setSelectedResource(null)
        }}
        onConfirm={handleConfirmReactivate}
      />

      <PermanentDeleteResourceModal
        opened={permanentDeleteOpened}
        resource={selectedResource}
        onClose={() => {
          setPermanentDeleteOpened(false)
          setSelectedResource(null)
        }}
        onConfirm={handleConfirmPermanentDelete}
      />
    </>
  )
}

export default ResourcesPage
