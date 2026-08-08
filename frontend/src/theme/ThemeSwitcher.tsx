import { SegmentedControl } from '@mantine/core'

import { useThemeMode } from './ThemeContext'

const ThemeSwitcher = () => {
  const { mode, setMode } = useThemeMode()

  return (
    <SegmentedControl
      size="xs"
      radius="xl"
      value={mode}
      onChange={(value) =>
        setMode(value as 'classic' | 'wood')
      }
      data={[
        {
          label: '☀ Classic',
          value: 'classic',
        },
        {
          label: '🌲 Wood',
          value: 'wood',
        },
      ]}
    />
  )
}

export default ThemeSwitcher