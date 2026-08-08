import { useState } from 'react'

import { resourceData } from '../mock/resourceData'
import type { Resource } from '../types'

const useResources = () => {
  const [resources, setResources] =
    useState<Resource[]>(resourceData)

  const addResource = (resource: Resource) => {
    setResources((prev) => [...prev, resource])
  }

  const updateResource = (resource: Resource) => {
    setResources((prev) =>
      prev.map((item) =>
        item.id === resource.id
          ? resource
          : item,
      ),
    )
  }

  const deleteResource = (id: number) => {
    setResources((prev) =>
      prev.filter((item) => item.id !== id),
    )
  }

  return {
    resources,
    addResource,
    updateResource,
    deleteResource,
  }
}

export default useResources