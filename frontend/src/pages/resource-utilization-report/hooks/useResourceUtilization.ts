import {
  bottlenecks,
  pieChartData,
  resources,
  summary,
} from '../mock/utilizationData'

const useResourceUtilization = () => {
  return {
    summary,

    resources,

    pieChartData,

    bottlenecks,
  }
}

export default useResourceUtilization