import { createTheme } from '@mantine/core'

export const classicTheme = createTheme({
   /** Primary color palette */
  primaryColor: 'blue',

  /** Default radius */
  defaultRadius: 'md',

  /** Font */
  fontFamily:
    'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',

  /** Colors */
  colors: {
    blue: [
      '#eff6ff',
      '#dbeafe',
      '#bfdbfe',
      '#93c5fd',
      '#60a5fa',
      '#3b82f6',
      '#2563eb',
      '#1d4ed8',
      '#1e40af',
      '#172554',
    ],
  },

  /** Headings */
  headings: {
    fontFamily:
      'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontWeight: '600',
  },

  /** Shadows */
  shadows: {
    xs: '0 1px 2px rgba(15,23,42,0.05)',
    sm: '0 2px 6px rgba(15,23,42,0.06)',
    md: '0 6px 16px rgba(15,23,42,0.08)',
    lg: '0 12px 28px rgba(15,23,42,0.10)',
  },

  /** Component Defaults */
  components: {
    Paper: {
      defaultProps: {
        radius: 'md',
        shadow: 'xs',
        p: 'md',
      },
    },

    Card: {
      defaultProps: {
        radius: 'md',
        shadow: 'xs',
        withBorder: true,
      },
    },

    Button: {
      defaultProps: {
        radius: 'md',
      },
    },

    TextInput: {
      defaultProps: {
        radius: 'md',
      },
    },

    Select: {
      defaultProps: {
        radius: 'md',
      },
    },

    NumberInput: {
      defaultProps: {
        radius: 'md',
      },
    },

    Modal: {
      defaultProps: {
        centered: true,
        radius: 'lg',
      },
    },
  },
})