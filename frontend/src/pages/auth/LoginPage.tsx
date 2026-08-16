import { useState } from 'react'

import {
  Alert,
  Anchor,
  Button,
  Center,
  Group,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'

import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import Logo from '../../components/common/Logo'
import { getApiErrorMessage } from '../../api/apiError'
import { useAuth } from '../../auth/AuthContext'

interface LoginLocationState {
  message?: string
}

const LoginPage = () => {
  const { login } = useAuth()
  const location = useLocation()

  // Set once by RegisterPage/ResetPasswordPage after a successful
  // action (navigate('/login', { state: { message: '...' } })) - not
  // persisted anywhere, so it naturally disappears on refresh/re-nav.
  const locationState = location.state as
    | LoginLocationState
    | null

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isValid =
    username.trim() !== '' && password !== ''

  const handleSubmit = async (
    event: React.FormEvent,
  ) => {
    event.preventDefault()

    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      await login(username, password)
    } catch (submitError) {
      setError(
        getApiErrorMessage(
          submitError,
          'Unable to log in. Please try again.',
        ),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Center
      h="100vh"
      style={{ background: '#F8FAFC' }}
    >
      <Paper
        w={380}
        p="xl"
        radius="md"
        withBorder
        shadow="sm"
      >
        <Stack gap="lg">
          <Logo />

          {locationState?.message && (
            <Alert
              color="green"
              icon={<CheckCircle2 size={18} />}
            >
              {locationState.message}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <Stack gap="md">
              <TextInput
                label="Username"
                placeholder="Enter your username"
                value={username}
                onChange={(e) =>
                  setUsername(e.currentTarget.value)
                }
                autoFocus
                autoComplete="username"
              />

              <PasswordInput
                label="Password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) =>
                  setPassword(e.currentTarget.value)
                }
                autoComplete="current-password"
              />

              <Group justify="flex-end">
                <Anchor
                  component={Link}
                  to="/forgot-password"
                  size="sm"
                >
                  Forgot password?
                </Anchor>
              </Group>

              {error && (
                <Alert
                  color="red"
                  icon={<AlertCircle size={18} />}
                >
                  {error}
                </Alert>
              )}

              <Button
                type="submit"
                fullWidth
                loading={isSubmitting}
                disabled={!isValid}
              >
                Log In
              </Button>

              <Text ta="center" size="sm">
                Don&apos;t have an account?{' '}
                <Anchor component={Link} to="/register">
                  Create account
                </Anchor>
              </Text>
            </Stack>
          </form>
        </Stack>
      </Paper>
    </Center>
  )
}

export default LoginPage
