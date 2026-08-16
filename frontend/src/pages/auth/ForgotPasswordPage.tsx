import { useState } from 'react'

import {
  Alert,
  Anchor,
  Button,
  Center,
  Paper,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'

import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import Logo from '../../components/common/Logo'
import { getApiErrorMessage } from '../../api/apiError'
import { forgotPasswordRequest } from '../../api/authApi'

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

const ForgotPasswordPage = () => {
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<
    string | null
  >(null)

  const isValid = EMAIL_PATTERN.test(email)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()

    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const response = await forgotPasswordRequest({ email })

      // Same generic message regardless of whether the email exists
      // - the backend deliberately never reveals that (see
      // backend/app/routers/auth.py::forgot_password) - shown here
      // exactly as returned, not reworded.
      setSuccessMessage(response.detail)
    } catch (submitError) {
      setError(
        getApiErrorMessage(
          submitError,
          'Unable to send reset link. Please try again.',
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

          {successMessage ? (
            <Stack gap="md">
              <Alert
                color="green"
                icon={<CheckCircle2 size={18} />}
              >
                {successMessage}
              </Alert>

              <Text ta="center" size="sm">
                <Anchor component={Link} to="/login">
                  Back to Login
                </Anchor>
              </Text>
            </Stack>
          ) : (
            <form onSubmit={handleSubmit}>
              <Stack gap="md">
                <Text size="sm" c="dimmed">
                  Enter the email associated with your account
                  and we&apos;ll send you a link to reset your
                  password.
                </Text>

                <TextInput
                  label="Email"
                  placeholder="you@example.com"
                  type="email"
                  value={email}
                  onChange={(e) =>
                    setEmail(e.currentTarget.value)
                  }
                  autoFocus
                  autoComplete="email"
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
                    ? 'Sending reset link...'
                    : 'Send Reset Link'}
                </Button>

                <Text ta="center" size="sm">
                  <Anchor component={Link} to="/login">
                    Back to Login
                  </Anchor>
                </Text>
              </Stack>
            </form>
          )}
        </Stack>
      </Paper>
    </Center>
  )
}

export default ForgotPasswordPage
