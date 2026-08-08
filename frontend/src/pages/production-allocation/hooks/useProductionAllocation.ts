import { useState } from 'react'

import {
  optimizationSummary,
  productionPlans,
} from '../mock/productionData'

const useProductionAllocation = () => {
  const [plans] =
    useState(productionPlans)

  const [summary] = useState(
    optimizationSummary,
  )

  const generatePlan = () => {
    console.log(
      'Generate Production Plan',
    )
  }

  return {
    plans,
    summary,
    generatePlan,
  }
}

export default useProductionAllocation