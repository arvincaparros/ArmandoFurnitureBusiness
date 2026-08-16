import { Alert, Badge, Modal, Stack, Text } from '@mantine/core'
import { Info } from 'lucide-react'

import type { UserResponse } from '../../api/types'

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

// Read-only: backend/app/schemas/auth.py's UserResponse only exposes
// id/username/is_active/created_at - no first/last name, email, or
// PATCH/update endpoint exists anywhere for the current user. Editable
// fields here would have nowhere to persist to, so this shows exactly
// what the existing GET /api/auth/me already returns rather than
// faking a save flow.
const ProfileModal = ({
  opened,
  onClose,
  user,
}: ProfileModalProps) => {
  const memberSince = user
    ? new Date(user.created_at).toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      })
    : '-'

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Profile"
      centered
    >
      <Stack gap="md">
        <Stack gap={4}>
          {fieldLabel('Username')}
          <Text>{user?.username ?? '-'}</Text>
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

        <Alert color="blue" icon={<Info size={16} />}>
          Profile editing isn&apos;t available yet - the backend
          doesn&apos;t currently expose an endpoint to update account
          details beyond what&apos;s shown here.
        </Alert>
      </Stack>
    </Modal>
  )
}

export default ProfileModal
