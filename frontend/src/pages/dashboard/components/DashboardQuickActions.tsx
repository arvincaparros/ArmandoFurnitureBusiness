import {
  Box,
  Button,
  Card,
  Grid,
  Stack,
  Text,
} from '@mantine/core'

import {
  Boxes,
  Package,
  Factory,
  FileBarChart,
  History,
} from 'lucide-react'

import { useNavigate } from 'react-router-dom'

import { useThemeMode } from '../../../theme/ThemeContext'

import classes from './DashboardQuickActions.module.css'

// Route strings kept local rather than imported from
// constants/navigation.ts, which is stale (missing Optimization
// History entirely, and its "History" entry points at /history -
// Transaction History, a different page) and isn't actually what
// drives navigation elsewhere either - layouts/sidebar/Sidebar.tsx
// keeps its own local {label, icon, path} list matching
// app/router.tsx exactly rather than importing it, and this follows
// that same established convention. Verified against router.tsx
// directly: Production Allocation lives at /production ("Generate
// Product Plan" takes the user to that existing workflow - it does
// NOT trigger generation itself), Optimization History at
// /optimization-history.
const actions = [
  {
    title: 'Manage Resources',
    icon: Boxes,
    path: '/resources',
  },
  {
    title: 'Manage Products Data',
    icon: Package,
    path: '/products',
  },
  {
    title: 'Generate Product Plan',
    icon: Factory,
    path: '/production',
  },
  {
    title: 'View Reports',
    icon: FileBarChart,
    path: '/reports',
  },
  {
    title: 'View History',
    icon: History,
    path: '/optimization-history',
  },
]

const DashboardQuickActions = () => {
  const navigate = useNavigate()
  const { mode } = useThemeMode()
  const isWood = mode === 'wood'

  return (
    <Card
      withBorder
      radius="md"
      p="md"
      style={
        isWood
          ? {
              backgroundColor: 'var(--card-bg)',
              backgroundImage: 'var(--card-bg-image)',
              borderColor: 'var(--card-border)',
              borderRadius: 14,
              boxShadow: 'var(--card-shadow)',
            }
          : undefined
      }
    >
      <Stack gap="md">
        <Text
          fw={600}
          style={
            isWood
              ? { fontFamily: 'var(--font-heading)', color: 'var(--ink-900)' }
              : undefined
          }
        >
          Quick Actions
        </Text>

        <Grid>
          {actions.map((action) => {
            const Icon = action.icon

            return (
              <Grid.Col
                key={action.title}
                span={{
                  base: 6,
                  sm: 4,
                  md: 2.4,
                }}
              >
                <Box h="100%">
                  <Card
                    withBorder
                    radius="md"
                    p="sm"
                    h="100%"
                    className={isWood ? classes.woodActionCard : undefined}
                    style={
                      isWood
                        ? {
                            backgroundColor: 'var(--cream-50)',
                            borderColor: 'var(--line)',
                            transition:
                              'border-color .15s, background .15s, transform .12s',
                          }
                        : undefined
                    }
                  >
                    <Button
                      variant="subtle"
                      fullWidth
                      className={
                        isWood ? classes.woodActionButton : undefined
                      }
                      leftSection={
                        <Icon
                          size={18}
                          color={
                            isWood ? 'var(--copper-500)' : undefined
                          }
                        />
                      }
                      style={
                        isWood
                          ? {
                              color: 'var(--ink-600)',
                              transition: 'transform .12s ease',
                            }
                          : undefined
                      }
                      styles={{
                        // Mantine's Button forces its label span to
                        // white-space: nowrap + overflow: hidden by
                        // default (styles/Button.css) - built for
                        // short, single-line labels, and exactly why
                        // "Manage Products Data"/"Generate Product
                        // Plan" were getting hard-clipped (not even
                        // ellipsized) inside these narrow 20%-width
                        // grid columns. Letting the label wrap - not
                        // shrinking the font or widening the grid -
                        // is what actually fixes it: root height
                        // switches from a fixed 100%/42 to auto with
                        // a 42 floor (unchanged for the three
                        // single-line labels, grows only for the two
                        // that need a second line) and drops the
                        // root's own overflow:hidden so a taller
                        // button is never self-clipped.
                        root: {
                          height: 'auto',
                          minHeight: 42,
                          overflow: 'visible',
                        },
                        label: {
                          whiteSpace: 'normal',
                          overflow: 'visible',
                          lineHeight: 1.2,
                        },
                      }}
                      onClick={() =>
                        navigate(action.path)
                      }
                    >
                      {action.title}
                    </Button>
                  </Card>
                </Box>
              </Grid.Col>
            )
          })}
        </Grid>
      </Stack>
    </Card>
  )
}


export default DashboardQuickActions