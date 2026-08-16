import apiClient from './client'

// Mirrors backend/app/schemas/production.py's ProductionCycleResponse.
export interface ProductionCycleResponse {
  id: number
  cycle_date: string
  start_date: string
  end_date: string
  status: string
}

// GET /api/production-cycles/latest - the canonical "latest
// production cycle" resolution (created_at DESC, id DESC), per the
// consistency audit that replaced each module's own duplicated
// "fetch the whole list and take the last item" logic. A 404 here
// means no production cycle exists yet - a legitimate empty state,
// not an error (same convention already used for the no-arg
// resource-utilization fetch).
export async function fetchLatestProductionCycle(): Promise<
  ProductionCycleResponse | null
> {
  try {
    const response = await apiClient.get<ProductionCycleResponse>(
      '/api/production-cycles/latest',
    )

    return response.data
  } catch (error) {
    if (
      typeof error === 'object' &&
      error !== null &&
      'response' in error &&
      (error as { response?: { status?: number } }).response
        ?.status === 404
    ) {
      return null
    }

    throw error
  }
}
