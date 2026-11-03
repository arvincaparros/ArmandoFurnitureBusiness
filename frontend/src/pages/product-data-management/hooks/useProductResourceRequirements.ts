import { useRef } from 'react'

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import { getApiErrorMessage } from '../../../api/apiError'

import {
  createProductResourceRequirement,
  deleteProductResourceRequirement,
  fetchAllResourcesForPicker,
  fetchProductResourceRequirements,
  updateProductResourceRequirement,
} from '../api/productResourceApi'

import {
  getAvailableResourcesForNewRequirement,
  resolveRequirements,
} from '../api/productResourceAdapter'

import type {
  ProductResourceRequirementCreateRequest,
  ProductResourceRequirementUpdateRequest,
} from '../api/productResourceTypes'

// Keyed by "<create|update|delete>:<resourceId>" so a create and an
// update for the same resource never clobber each other's tracked
// promise/failure entry.
type MutationKey = string

export interface ResourceRequirementFailure {
  resourceId: number
  resourceName: string
  message: string
}

const useProductResourceRequirements = (
  productId: number,
) => {
  const queryClient = useQueryClient()

  // Tracks every in-flight create/update/delete so a caller (the Add/
  // Edit Product modal's "Save Changes") can wait for all of them to
  // settle before deciding whether the overall save succeeded - each
  // RequirementRow/add-form saves independently on its own blur/
  // confirm, with no other link back to the modal's own submit flow.
  const pendingMutationsRef = useRef<
    Map<MutationKey, Promise<unknown>>
  >(new Map())

  const mutationFailuresRef = useRef<
    Map<MutationKey, { resourceId: number; message: string }>
  >(new Map())

  const requirementsQueryKey = [
    'product-resources',
    productId,
  ]

  const requirementsQuery = useQuery({
    queryKey: requirementsQueryKey,
    queryFn: () =>
      fetchProductResourceRequirements(productId),
  })

  const resourcesQuery = useQuery({
    queryKey: ['resources-all'],
    queryFn: fetchAllResourcesForPicker,
  })

  const invalidateRequirements = () =>
    queryClient.invalidateQueries({
      queryKey: requirementsQueryKey,
    })

  const createMutation = useMutation({
    mutationFn: (
      data: ProductResourceRequirementCreateRequest,
    ) =>
      createProductResourceRequirement(productId, data),
    onSuccess: invalidateRequirements,
  })

  const updateMutation = useMutation({
    mutationFn: ({
      resourceId,
      data,
    }: {
      resourceId: number
      data: ProductResourceRequirementUpdateRequest
    }) =>
      updateProductResourceRequirement(
        productId,
        resourceId,
        data,
      ),
    onSuccess: invalidateRequirements,
  })

  const deleteMutation = useMutation({
    mutationFn: (resourceId: number) =>
      deleteProductResourceRequirement(
        productId,
        resourceId,
      ),
    onSuccess: invalidateRequirements,
  })

  const rawRequirements = requirementsQuery.data ?? []
  const resources = resourcesQuery.data ?? []

  const trackMutation = <T,>(
    key: MutationKey,
    resourceId: number,
    promise: Promise<T>,
  ): Promise<T> => {
    const tracked = promise
      .then((result) => {
        mutationFailuresRef.current.delete(key)
        return result
      })
      .catch((error: unknown) => {
        mutationFailuresRef.current.set(key, {
          resourceId,
          message: getApiErrorMessage(
            error,
            'Unable to save this resource requirement.',
          ),
        })
        throw error
      })
      .finally(() => {
        pendingMutationsRef.current.delete(key)
      })

    pendingMutationsRef.current.set(key, tracked)

    return tracked
  }

  const createRequirement = (
    data: ProductResourceRequirementCreateRequest,
  ) =>
    trackMutation(
      `create:${data.resource_id}`,
      data.resource_id,
      createMutation.mutateAsync(data),
    )

  const updateRequirement = (args: {
    resourceId: number
    data: ProductResourceRequirementUpdateRequest
  }) =>
    trackMutation(
      `update:${args.resourceId}`,
      args.resourceId,
      updateMutation.mutateAsync(args),
    )

  const deleteRequirement = (resourceId: number) =>
    trackMutation(
      `delete:${resourceId}`,
      resourceId,
      deleteMutation.mutateAsync(resourceId),
    )

  // Awaits every mutation currently in flight (started by a row's own
  // blur save or the add-form's confirm, independently of this
  // caller) and reports which resources - by name, since the caller
  // has no other way to identify them - ended up rejected. Clears the
  // failure set it reports so a later, unrelated call does not keep
  // re-reporting a failure the caller already surfaced once.
  const waitForPendingChanges = async (): Promise<
    ResourceRequirementFailure[]
  > => {
    const pending = Array.from(
      pendingMutationsRef.current.values(),
    )

    await Promise.allSettled(pending)

    const failures = Array.from(
      mutationFailuresRef.current.values(),
    ).map((failure) => ({
      ...failure,
      resourceName:
        resources.find(
          (resource) => resource.id === failure.resourceId,
        )?.name ?? `Resource #${failure.resourceId}`,
    }))

    mutationFailuresRef.current.clear()

    return failures
  }

  return {
    requirements: resolveRequirements(
      rawRequirements,
      resources,
    ),
    availableResourcesForNew:
      getAvailableResourcesForNewRequirement(
        resources,
        rawRequirements,
      ),

    isLoading:
      requirementsQuery.isLoading || resourcesQuery.isLoading,
    isError:
      requirementsQuery.isError || resourcesQuery.isError,

    createRequirement,
    updateRequirement,
    deleteRequirement,
    waitForPendingChanges,
  }
}

export default useProductResourceRequirements
