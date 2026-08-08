import { createTheme } from '@mantine/core'

export const woodTheme = createTheme({
  primaryColor: 'wood',

  defaultRadius: 'md',

  colors: {
    wood: [
      '#FCF8F2',
      '#F5E8D7',
      '#EDD6BA',
      '#DFBE95',
      '#D2A46D',
      '#B9824A',
      '#9D6836',
      '#7E522C',
      '#654324',
      '#4C311D',
    ],
  },

  components: {
    Card: {
      defaultProps: {
        radius: 'md',
        withBorder: true,
      },
    },

    Button: {
      defaultProps: {
        radius: 'md',
      },
    },
  },
})