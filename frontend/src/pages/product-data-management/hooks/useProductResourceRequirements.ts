import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

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

const useProductResourceRequirements = (
  productId: number,
) => {
  const queryClient = useQueryClient()

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

    createRequirement: createMutation.mutateAsync,
    updateRequirement: updateMutation.mutateAsync,
    deleteRequirement: deleteMutation.mutateAsync,
  }
}

export default useProductResourceRequirements
