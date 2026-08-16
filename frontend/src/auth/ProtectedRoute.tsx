import { Center, Loader } from '@mantine/core'
import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from './AuthContext'

// Guards the authenticated app shell. Redirect target (/login) is
// itself guarded by GuestRoute the opposite way, so the two can
// never bounce a user back and forth.
const ProtectedRoute = () => {
  const { status } = useAuth()

  if (status === 'initializing') {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}

export default ProtectedRoute
