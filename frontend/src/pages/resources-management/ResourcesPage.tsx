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
import useResources from './hooks/useResources'

import { notify } from '../../utils/notify'

const ResourcesPage = () => {
  const [opened, setOpened] = useState(false)

  const [selectedResource, setSelectedResource] =
  useState<Resource | null>(null)
  
  const [deleteOpened, setDeleteOpened] = useState(false)

  const [search, setSearch] = useState('')

  const [sortBy, setSortBy] = useState<keyof Resource>('resourceType')

  const [reverse, setReverse] = useState(false)

  const {
    resources,
    addResource,
    updateResource,
    deleteResource,
  } = useResources()

  const handleSave = () => {
    notify.saved()
  }

  const filteredResources = resources.filter((resource) =>
    resource.resourceType
      .toLowerCase()
      .includes(search.toLowerCase()),
  )

  const sortedResources = [...filteredResources].sort(
    (a, b) => {
      const aValue = a[sortBy]
      const bValue = b[sortBy]

      if (aValue < bValue)
        return reverse ? 1 : -1

      if (aValue > bValue)
        return reverse ? -1 : 1

      return 0
    },
  )

  const handleSaveResource = (resource: Resource) => {
    if (selectedResource) {
      updateResource(resource)

      notify.updated(resource.resourceType)

    } else {
      addResource(resource)

      notify.added(resource.resourceType)
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

  const handleConfirmDelete = () => {
    if (!selectedResource) return

    deleteResource(selectedResource.id)

    notify.deleted(selectedResource.resourceType)

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
        onSave={handleSave}
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
          sortBy={sortBy}
          reverse={reverse}
          onSort={handleSort}
        />
      </ChartCard>

      <AddResourceModal
        opened={opened}
        resource={selectedResource}
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