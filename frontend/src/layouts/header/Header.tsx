import {
  ActionIcon,
  Avatar,
  Burger,
  Group,
  Menu,
} from '@mantine/core'

import {
  Bell,
  ChevronDown,
  LogOut,
  Settings,
  User,
} from 'lucide-react'

import Logo from '../../components/common/Logo'

interface HeaderProps {
  opened: boolean
  toggle: () => void
}

const Header = ({
  opened,
  toggle,
}: HeaderProps) => {

  return (
    <Group
      h="100%"
      px="lg"
      justify="space-between"
    >
      <Group gap="lg">
        <Burger
          opened={opened}
          onClick={toggle}
          hiddenFrom="sm"
        />

        <Logo />
      </Group>

      <Group gap="sm">
        <ActionIcon
          variant="subtle"
          size="lg"
        >
          <Bell size={18} />
        </ActionIcon>

        <Menu shadow="md" width={220}>
          <Menu.Target>
            <Group
              gap={8}
              style={{ cursor: 'pointer' }}
            >
              <Avatar
                radius="xl"
                color="blue"
              >
                A
              </Avatar>

              <ChevronDown size={16} />
            </Group>
          </Menu.Target>

          <Menu.Dropdown>
            <Menu.Label>Account</Menu.Label>

            <Menu.Item
              leftSection={<User size={16} />}
            >
              Profile
            </Menu.Item>

            <Menu.Item
              leftSection={<Settings size={16} />}
            >
              Settings
            </Menu.Item>

            <Menu.Divider />

            <Menu.Item
              color="red"
              leftSection={<LogOut size={16} />}
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