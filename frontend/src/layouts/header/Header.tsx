import { useState } from 'react'

import {
  Avatar,
  Box,
  Burger,
  Group,
  Menu,
} from '@mantine/core'

import {
  ChevronDown,
  LogOut,
  User,
} from 'lucide-react'

import Logo from '../../components/common/Logo'
import ThemeSwitcher from '../../theme/ThemeSwitcher'
import { useThemeMode } from '../../theme/ThemeContext'
import { useAuth } from '../../auth/AuthContext'
import { getUserInitials } from '../../utils/userInitials'

import ProfileModal from './ProfileModal'

interface HeaderProps {
  opened: boolean
  toggle: () => void
}

const Header = ({
  opened,
  toggle,
}: HeaderProps) => {
  const { mode } = useThemeMode()
  const { user, logout } = useAuth()

  const [profileOpened, setProfileOpened] = useState(false)

  return (
    <>
      <Group
        justify="space-between"
        h="100%"
        px="md"
      >
        <Group gap="sm">
          <Burger
            opened={opened}
            onClick={toggle}
            hiddenFrom="sm"
            size="sm"
          />

          <Logo />
        </Group>

        <Group gap="sm">
          {/* Desktop only */}
          <Box visibleFrom="md">
            <ThemeSwitcher />
          </Box>

          <Menu shadow="md" width={220}>
            <Menu.Target>
              <Group
                gap={8}
                style={{ cursor: 'pointer' }}
              >
                <Avatar
                  radius="xl"
                  color={
                    mode === 'wood'
                      ? 'wood'
                      : 'blue'
                  }
                >
                  {getUserInitials(user?.username)}
                </Avatar>

                <Box visibleFrom="md">
                  <ChevronDown size={16} />
                </Box>
              </Group>
            </Menu.Target>

            <Menu.Dropdown>
              <Menu.Label>
                {user?.username ?? 'Account'}
              </Menu.Label>

              <Menu.Item
                leftSection={<User size={16} />}
                onClick={() => setProfileOpened(true)}
              >
                Profile
              </Menu.Item>

              <Menu.Divider />

              <Menu.Item
                color="red"
                leftSection={
                  <LogOut size={16} />
                }
                onClick={() => {
                  void logout()
                }}
              >
                Logout
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>

      <ProfileModal
        opened={profileOpened}
        user={user}
        onClose={() => setProfileOpened(false)}
      />
    </>
  )
}

export default Header
