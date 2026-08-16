import { useState } from 'react'

import { Search } from 'lucide-react'
import { TextInput } from '@mantine/core'

import PageHeader from '../../components/common/PageHeader'
import ChartCard from '../../components/cards/ChartCard'

import AddResourceModal from './components/AddResourceModal'
import ResourceTable from './components/ResourceTable'
import ResourceToolbar from './components/ResourceToolbar'
import DeleteResourceModal from './components/DeleteResourceModal'

import type { Resource } from './types'
import type {
  ResourceCreateRequest,
  ResourceUpdateRequest,
} from './api/resourceTypes'
import useResources from './hooks/useResources'

import { notify } from '../../utils/notify'

const ResourcesPage = () => {
  const [opened, setOpened] = useState(false)

  const [selectedResource, setSelectedResource] =
  useState<Resource | null>(null)

  const [deleteOpened, setDeleteOpened] = useState(false)

  const [search, setSearch] = useState('')

  const [sortBy, setSortBy] = useState<keyof Resource>('name')

  const [reverse, setReverse] = useState(false)

  const {
    resources,
    isLoading,
    isError,
    hasCycle,
    createResource,
    updateResource,
    deleteResource,
    savePricing,
  } = useResources()

  const filteredResources = resources.filter((resource) =>
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
    payload: ResourceCreateRequest | ResourceUpdateRequest,
    pricing: { available_quantity: number; unit_price: number } | null,
  ) => {
    let resourceId: number

    if (selectedResource) {
      await updateResource({
        id: selectedResource.id,
        data: payload,
      })

      resourceId = selectedResource.id

      notify.updated(payload.name ?? selectedResource.name)
    } else {
      const created = await createResource(
        payload as ResourceCreateRequest,
      )

      resourceId = created.id

      notify.added(payload.name ?? '')
    }

    // Availability/price are a second write against CycleResource
    // (see useResources.ts) - only attempted when the modal actually
    // collected them (a production cycle exists), so creating a
    // resource with no cycle yet still succeeds for its global
    // fields.
    if (pricing) {
      await savePricing({ resourceId, data: pricing })
    }

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
      />

      <ChartCard
        title="Resources"
        subtitle={`Current inventory list • ${filteredResources.length} resource${filteredResources.length !== 1 ? 's' : ''}`}
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
          isLoading={isLoading}
          isError={isError}
          sortBy={sortBy}
          reverse={reverse}
          onSort={handleSort}
        />
      </ChartCard>

      <AddResourceModal
        opened={opened}
        resource={selectedResource}
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
    </>
  )
}

export default ResourcesPage
