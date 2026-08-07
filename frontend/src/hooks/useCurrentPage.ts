import { useLocation } from 'react-router-dom'

import { navigation } from '../constants/navigation'

const useCurrentPage = () => {
  const location = useLocation()

  return (
    navigation.find(
      (item) => item.path === location.pathname
    )?.label ?? ''
  )
}

export default useCurrentPage