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
  Settings,
  User,
} from 'lucide-react'

import Logo from '../../components/common/Logo'
import ThemeSwitcher from '../../theme/ThemeSwitcher'
import { useThemeMode } from '../../theme/ThemeContext'

interface HeaderProps {
  opened: boolean
  toggle: () => void
}

const Header = ({
  opened,
  toggle,
}: HeaderProps) => {
  const { mode } = useThemeMode()

  return (
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
                A
              </Avatar>

              <Box visibleFrom="md">
                <ChevronDown size={16} />
              </Box>
            </Group>
          </Menu.Target>

          <Menu.Dropdown>
            <Menu.Label>
              Account
            </Menu.Label>

            <Menu.Item
              leftSection={<User size={16} />}
            >
              Profile
            </Menu.Item>

            <Menu.Item
              leftSection={
                <Settings size={16} />
              }
            >
              Settings
            </Menu.Item>

            <Menu.Divider />

            <Menu.Item
              color="red"
              leftSection={
                <LogOut size={16} />
              }
            >
              Logout
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>
    </Group>
  )
}

export default Header