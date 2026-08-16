import { Center, Loader } from '@mantine/core'
import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from './AuthContext'

// Guards /login. An already-authenticated user is sent to the
// authenticated landing page instead of seeing the login form
// again; ProtectedRoute does the mirror-image check.
const GuestRoute = () => {
  const { status } = useAuth()

  if (status === 'initializing') {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  }

  if (status === 'authenticated') {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}

export default GuestRoute
