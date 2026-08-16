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
} from '@mantine/core'

import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import Logo from '../../components/common/Logo'
import { getApiErrorMessage } from '../../api/apiError'
import { resetPasswordRequest } from '../../api/authApi'

const PASSWORD_MIN_LENGTH = 8

const ResetPasswordPage = () => {
  // Token travels as a query param, never in the request body's URL
  // or a route segment that could end up logged - matches the
  // approved architecture (/reset-password?token=...).
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<
    string | null
  >(null)

  const isValid =
    newPassword.length >= PASSWORD_MIN_LENGTH
    && confirmPassword === newPassword

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()

    if (!token || !isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const response = await resetPasswordRequest({
        token,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })

      setSuccessMessage(response.detail)
    } catch (submitError) {
      setError(
        getApiErrorMessage(
          submitError,
          'Unable to reset password. The link may be invalid or expired.',
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

          {!token ? (
            <Stack gap="md">
              <Alert
                color="red"
                icon={<AlertCircle size={18} />}
              >
                This password reset link is missing or invalid.
                Request a new one from the login page.
              </Alert>

              <Text ta="center" size="sm">
                <Anchor component={Link} to="/forgot-password">
                  Request a new reset link
                </Anchor>
              </Text>
            </Stack>
          ) : successMessage ? (
            <Stack gap="md">
              <Alert
                color="green"
                icon={<CheckCircle2 size={18} />}
              >
                {successMessage}
              </Alert>

              <Button
                component={Link}
                to="/login"
                fullWidth
              >
                Go to Login
              </Button>
            </Stack>
          ) : (
            <form onSubmit={handleSubmit}>
              <Stack gap="md">
                <PasswordInput
                  label="New Password"
                  placeholder="At least 8 characters"
                  value={newPassword}
                  onChange={(e) =>
                    setNewPassword(e.currentTarget.value)
                  }
                  autoFocus
                  autoComplete="new-password"
                />

                <PasswordInput
                  label="Confirm Password"
                  placeholder="Re-enter your new password"
                  value={confirmPassword}
                  onChange={(e) =>
                    setConfirmPassword(e.currentTarget.value)
                  }
                  autoComplete="new-password"
                  error={
                    confirmPassword !== ''
                    && confirmPassword !== newPassword
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
                    ? 'Resetting password...'
                    : 'Reset Password'}
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

export default ResetPasswordPage
