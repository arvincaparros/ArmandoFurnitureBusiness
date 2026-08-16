import { useState } from 'react'

import {
  Alert,
  Button,
  Center,
  Paper,
  PasswordInput,
  Stack,
  TextInput,
} from '@mantine/core'

import { AlertCircle } from 'lucide-react'

import Logo from '../../components/common/Logo'
import { getApiErrorMessage } from '../../api/apiError'
import { useAuth } from '../../auth/AuthContext'

const LoginPage = () => {
  const { login } = useAuth()

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
            </Stack>
          </form>
        </Stack>
      </Paper>
    </Center>
  )
}

export default LoginPage
