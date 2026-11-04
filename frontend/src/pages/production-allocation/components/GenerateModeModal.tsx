import { useState } from 'react'

import {
  Badge,
  Button,
  Group,
  Modal,
  Radio,
  Stack,
  Text,
} from '@mantine/core'

import { Factory, TrendingUp } from 'lucide-react'

import type { PlanningMode } from '../api/productionTypes'

import classes from './GenerateModeModal.module.css'

interface GenerateModeModalProps {
  opened: boolean
  selectedMode: PlanningMode
  onSelectMode: (mode: PlanningMode) => void
  onCancel: () => void
  onContinue: () => void
}

// Mantine unmounts a Modal's children on close by default (no
// keepMounted here), so this component's own local state - the
// duplicate-click guard below - is fresh every time it reopens with
// no explicit reset needed. selectedMode itself lives in the parent
// (useProductionAllocation's planningMode state), not here, so it
// naturally survives Cancel and a later reopen.
const GenerateModeModal = ({
  opened,
  selectedMode,
  onSelectMode,
  onCancel,
  onContinue,
}: GenerateModeModalProps) => {
  // Belt-and-suspenders duplicate-request guard: disables the button
  // AND short-circuits the handler itself, so even a double-click
  // landing before the disabled attribute re-renders can only ever
  // call onContinue once per time this modal is open.
  const [hasStarted, setHasStarted] = useState(false)

  const handleContinue = () => {
    if (hasStarted) {
      return
    }

    setHasStarted(true)
    onContinue()
  }

  return (
    <Modal
      opened={opened}
      onClose={onCancel}
      title="Generate Production Plan"
      centered
      size="md"
    >
      <Text c="dimmed" mb="md">
        Select how you want to optimize your production.
      </Text>

      <Radio.Group
        value={selectedMode}
        onChange={(value) => onSelectMode(value as PlanningMode)}
      >
        <Stack gap="sm">
          <Radio.Card
            value="demand_based"
            p="md"
            radius="md"
            classNames={{ card: classes.card }}
          >
            <Group
              wrap="nowrap"
              align="flex-start"
            >
              <Radio.Indicator mt={2} />

              <div style={{ flex: 1 }}>
                <Group gap="xs">
                  <TrendingUp size={16} />
                  <Text fw={600}>Demand-Based Optimization</Text>
                </Group>

                <Text
                  size="sm"
                  c="dimmed"
                  mt={4}
                >
                  Uses sales forecasts to limit production quantities
                  and help prevent overproduction.
                </Text>
              </div>
            </Group>
          </Radio.Card>

          <Radio.Card
            value="resource_based"
            p="md"
            radius="md"
            classNames={{ card: classes.card }}
          >
            <Group
              wrap="nowrap"
              align="flex-start"
            >
              <Radio.Indicator mt={2} />

              <div style={{ flex: 1 }}>
                <Group gap="xs">
                  <Factory size={16} />
                  <Text fw={600}>Resource-Based Optimization</Text>
                </Group>

                <Text
                  size="sm"
                  c="dimmed"
                  mt={4}
                >
                  Maximizes production profitability based on
                  available resources without sales forecast
                  ceilings.
                </Text>

                <Badge
                  color="teal"
                  variant="light"
                  mt="sm"
                >
                  Recommended · Default
                </Badge>
              </div>
            </Group>
          </Radio.Card>
        </Stack>
      </Radio.Group>

      <Group
        justify="flex-end"
        mt="lg"
      >
        <Button
          variant="default"
          onClick={onCancel}
          disabled={hasStarted}
        >
          Cancel
        </Button>

        <Button
          onClick={handleContinue}
          disabled={hasStarted}
        >
          Continue
        </Button>
      </Group>
    </Modal>
  )
}

export default GenerateModeModal
