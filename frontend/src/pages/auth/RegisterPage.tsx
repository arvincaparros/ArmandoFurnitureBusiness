import { useState } from 'react'

import {
  Alert,
  Anchor,
  Button,
  Center,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'

import { AlertCircle } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import Logo from '../../components/common/Logo'
import { getApiErrorMessage } from '../../api/apiError'
import { registerRequest } from '../../api/authApi'

// Same policy the backend enforces (backend/app/schemas/auth.py's
// PASSWORD_MIN_LENGTH) - checked here too only so the user sees a
// clear inline message before submitting, not as the source of
// truth (the backend re-validates and is authoritative).
const PASSWORD_MIN_LENGTH = 8

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

const RegisterPage = () => {
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isValid =
    username.trim() !== ''
    && EMAIL_PATTERN.test(email)
    && password.length >= PASSWORD_MIN_LENGTH
    && confirmPassword === password

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()

    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      await registerRequest({
        username,
        email,
        password,
        confirm_password: confirmPassword,
      })

      navigate('/login', {
        state: {
          message: 'Account created successfully. Please log in.',
        },
      })
    } catch (submitError) {
      setError(
        getApiErrorMessage(
          submitError,
          'Unable to create account. Please try again.',
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
                placeholder="Choose a username"
                value={username}
                onChange={(e) =>
                  setUsername(e.currentTarget.value)
                }
                autoFocus
                autoComplete="username"
              />

              <TextInput
                label="Email"
                placeholder="you@example.com"
                type="email"
                value={email}
                onChange={(e) =>
                  setEmail(e.currentTarget.value)
                }
                autoComplete="email"
                error={
                  email !== '' && !EMAIL_PATTERN.test(email)
                    ? 'Enter a valid email address'
                    : undefined
                }
              />

              <PasswordInput
                label="Password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) =>
                  setPassword(e.currentTarget.value)
                }
                autoComplete="new-password"
              />

              <PasswordInput
                label="Confirm Password"
                placeholder="Re-enter your password"
                value={confirmPassword}
                onChange={(e) =>
                  setConfirmPassword(e.currentTarget.value)
                }
                autoComplete="new-password"
                error={
                  confirmPassword !== ''
                  && confirmPassword !== password
                    ? 'Passwords do not match'
                    : undefined
                }
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
                {isSubmitting
                  ? 'Creating account...'
                  : 'Create Account'}
              </Button>

              <Text ta="center" size="sm">
                <Anchor component={Link} to="/login">
                  Back to Login
                </Anchor>
              </Text>
            </Stack>
          </form>
        </Stack>
      </Paper>
    </Center>
  )
}

export default RegisterPage
