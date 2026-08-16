import { useState } from 'react'

import {
  Alert,
  Badge,
  Button,
  Divider,
  Modal,
  PasswordInput,
  Stack,
  Text,
} from '@mantine/core'

import { AlertCircle, CheckCircle2 } from 'lucide-react'

import type { UserResponse } from '../../api/types'
import { getApiErrorMessage } from '../../api/apiError'
import { changePasswordRequest } from '../../api/authApi'

// Same policy the backend enforces (backend/app/schemas/auth.py's
// PASSWORD_MIN_LENGTH) - checked here only for immediate inline
// feedback; the backend re-validates and is authoritative.
const PASSWORD_MIN_LENGTH = 8

interface ProfileModalProps {
  opened: boolean
  onClose: () => void
  user: UserResponse | null
}

const fieldLabel = (label: string) => (
  <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
    {label}
  </Text>
)

const ProfileModal = ({
  opened,
  onClose,
  user,
}: ProfileModalProps) => {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<
    string | null
  >(null)

  const memberSince = user
    ? new Date(user.created_at).toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      })
    : '-'

  const isValid =
    currentPassword !== ''
    && newPassword.length >= PASSWORD_MIN_LENGTH
    && confirmPassword === newPassword
    && newPassword !== currentPassword

  const resetForm = () => {
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
  }

  const handleChangePassword = async (
    event: React.FormEvent,
  ) => {
    event.preventDefault()

    if (!isValid || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const response = await changePasswordRequest({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })

      // Session is deliberately left intact - the existing JWT stays
      // valid (it doesn't encode the password), so there's nothing
      // in the current architecture that requires logging the user
      // out just because their password changed.
      setSuccessMessage(response.detail)
      resetForm()
    } catch (submitError) {
      setError(
        getApiErrorMessage(
          submitError,
          'Unable to change password. Please try again.',
        ),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    resetForm()
    setError(null)
    setSuccessMessage(null)
    onClose()
  }

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title="Profile"
      centered
    >
      <Stack gap="md">
        <Stack gap={4}>
          {fieldLabel('Username')}
          <Text>{user?.username ?? '-'}</Text>
        </Stack>

        <Stack gap={4}>
          {fieldLabel('Email')}
          <Text>{user?.email ?? '-'}</Text>
        </Stack>

        <Stack gap={4}>
          {fieldLabel('Account Status')}
          <Badge
            color={user?.is_active ? 'green' : 'gray'}
            variant="light"
          >
            {user?.is_active ? 'Active' : 'Inactive'}
          </Badge>
        </Stack>

        <Stack gap={4}>
          {fieldLabel('Member Since')}
          <Text>{memberSince}</Text>
        </Stack>

        <Divider label="Change Password" labelPosition="left" />

        <form onSubmit={handleChangePassword}>
          <Stack gap="sm">
            <PasswordInput
              label="Current Password"
              value={currentPassword}
              onChange={(e) =>
                setCurrentPassword(e.currentTarget.value)
              }
              autoComplete="current-password"
            />

            <PasswordInput
              label="New Password"
              placeholder="At least 8 characters"
              value={newPassword}
              onChange={(e) =>
                setNewPassword(e.currentTarget.value)
              }
              autoComplete="new-password"
              error={
                newPassword !== ''
                && currentPassword !== ''
                && newPassword === currentPassword
                  ? 'New password must be different from the current password'
                  : undefined
              }
            />

            <PasswordInput
              label="Confirm New Password"
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
                icon={<AlertCircle size={16} />}
              >
                {error}
              </Alert>
            )}

            {successMessage && (
              <Alert
                color="green"
                icon={<CheckCircle2 size={16} />}
              >
                {successMessage}
              </Alert>
            )}

            <Button
              type="submit"
              loading={isSubmitting}
              disabled={!isValid}
            >
              {isSubmitting
                ? 'Changing password...'
                : 'Change Password'}
            </Button>
          </Stack>
        </form>
      </Stack>
    </Modal>
  )
}

export default ProfileModal
