import { createTheme } from '@mantine/core'

export const woodTheme = createTheme({
  primaryColor: 'wood',

  defaultRadius: 14,

  fontFamily: 'var(--font-body)',

  headings: {
    fontFamily: 'var(--font-heading)',
    fontWeight: '600',
  },

  colors: {
    wood: [
      '#FBF5EA',
      '#F6ECDB',
      '#EAD9BC',
      '#DDB88B',
      '#C89660',
      '#C2792E',
      '#B5651D',
      '#9A5417',
      '#8B5A2B',
      '#4A2A17',
    ],
  },

  shadows: {
    xs: '0 1px 2px rgba(43,26,16,0.06)',
    sm: '0 1px 2px rgba(43,26,16,0.06), 0 8px 24px -8px rgba(43,26,16,0.18)',
    md: '0 1px 2px rgba(43,26,16,0.06), 0 8px 24px -8px rgba(43,26,16,0.18)',
    lg: '0 4px 12px -3px rgba(154,84,23,0.35)',
  },

  components: {
    Card: {
      defaultProps: {
        radius: 14,
        withBorder: true,
      },
    },

    Button: {
      defaultProps: {
        radius: 10,
      },
    },
  },
})
