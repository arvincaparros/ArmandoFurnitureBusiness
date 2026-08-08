import { useEffect, useState } from 'react'

import {
  Button,
  Divider,
  Group,
  Modal,
  NumberInput,
  SimpleGrid,
  Stack,
  TextInput,
} from '@mantine/core'

import type { Product } from '../types'

interface AddProductModalProps {
  opened: boolean
  onClose: () => void
  onSave: (product: Product) => void
  product?: Product | null
}

const AddProductModal = ({
  opened,
  onClose,
  onSave,
  product,
}: AddProductModalProps) => {
  const [productName, setProductName] =
    useState('')

  const [wood, setWood] = useState(0)
  const [epoxy, setEpoxy] = useState(0)
  const [nails, setNails] = useState(0)
  const [glue, setGlue] = useState(0)
  const [sandpaper, setSandpaper] =
    useState(0)
  const [doorknob, setDoorknob] =
    useState(0)

  const [laborHours, setLaborHours] =
    useState(0)

  const [sawHours, setSawHours] =
    useState(0)

  const [
    thicknessPlanerHours,
    setThicknessPlanerHours,
  ] = useState(0)

  const [
    handPlanerHours,
    setHandPlanerHours,
  ] = useState(0)

  const [sellingPrice, setSellingPrice] =
    useState(0)

  useEffect(() => {
    if (product) {
      setProductName(product.productName)

      setWood(product.wood)
      setEpoxy(product.epoxy)
      setNails(product.nails)
      setGlue(product.glue)
      setSandpaper(product.sandpaper)
      setDoorknob(product.doorknob)

      setLaborHours(product.laborHours)

      setSawHours(product.sawHours)
      setThicknessPlanerHours(
        product.thicknessPlanerHours,
      )
      setHandPlanerHours(
        product.handPlanerHours,
      )

      setSellingPrice(product.sellingPrice)
    } else {
      setProductName('')

      setWood(0)
      setEpoxy(0)
      setNails(0)
      setGlue(0)
      setSandpaper(0)
      setDoorknob(0)

      setLaborHours(0)

      setSawHours(0)
      setThicknessPlanerHours(0)
      setHandPlanerHours(0)

      setSellingPrice(0)
    }
  }, [product, opened])

  const isValid =
    productName.trim() !== '' &&
    sellingPrice > 0

  const handleSave = () => {
    const materialCost = 0
    const laborCost = 0
    const machineCost = 0

    const totalCost =
        materialCost + laborCost + machineCost

    const profit =
        sellingPrice - totalCost

    onSave({
      id: product?.id ?? Date.now(),
  
      productName,
  
      wood,
      epoxy,
      nails,
      glue,
      sandpaper,
      doorknob,
  
      laborHours,
  
      sawHours,
      thicknessPlanerHours,
      handPlanerHours,
  
      sellingPrice,
  
      materialCost,
      laborCost,
      machineCost,
      totalCost,
      profit,
    })

    onClose()
  }

  return (
    <Modal
        opened={opened}
        onClose={onClose}
        title={product ? 'Edit Product' : 'Add Product'}
        size="xl"
        centered
        radius="lg"
        styles={{
            content: {
            borderRadius: 16,
            overflow: 'hidden',
            },
        }}
    >
      <Stack gap="xs">
        <SimpleGrid cols={2}>
            <TextInput
            radius="md"
            label="Product Name"
            placeholder="e.g. Dining Table"
            value={productName}
            onChange={(e) =>
                setProductName(e.currentTarget.value)
            }
            />

            <NumberInput
            radius="md"
            label="Selling Price"
            value={sellingPrice}
            prefix="₱"
            thousandSeparator=","
            onChange={(value) =>
                setSellingPrice(Number(value))
            }
            />
        </SimpleGrid>

        <Divider
            my="xs"
            label="Resource Usage"
            labelPosition="center"
        />

        <SimpleGrid cols={2}>
            <NumberInput
                radius="md"
                label="Wood"
                value={wood}
                onChange={(v) => setWood(Number(v))}
            />

            <NumberInput
                radius="md"
                label="Epoxy"
                value={epoxy}
                onChange={(v) => setEpoxy(Number(v))}
            />

            <NumberInput
                radius="md"
                label="Nails"
                value={nails}
                onChange={(v) => setNails(Number(v))}
            />

            <NumberInput
                radius="md"
                label="Glue"
                value={glue}
                onChange={(v) => setGlue(Number(v))}
            />

            <NumberInput
                radius="md"
                label="Sandpaper"
                value={sandpaper}
                onChange={(v) =>
                    setSandpaper(Number(v))
                }
            />

            <NumberInput
                radius="md"
                label="Doorknob"
                value={doorknob}
                onChange={(v) =>
                    setDoorknob(Number(v))
                }
            />
        </SimpleGrid>

        <Divider
            my="xs"
            label="Machine & Labor"
            labelPosition="center"
        />

        <SimpleGrid cols={2}>
            <NumberInput
                radius="md"
                label="Saw Hours"
                value={sawHours}
                onChange={(v) =>
                    setSawHours(Number(v))
                }
            />

            <NumberInput
                radius="md"
                label="Labor Hours"
                value={laborHours}
                onChange={(v) =>
                    setLaborHours(Number(v))
                }
            />

            <NumberInput
                radius="md"
                label="Thickness Planer"
                value={thicknessPlanerHours}
                onChange={(v) =>
                    setThicknessPlanerHours(
                    Number(v),
                    )
                }
            />

            <NumberInput
                radius="md"
                label="Hand Planer"
                value={handPlanerHours}
                onChange={(v) =>
                    setHandPlanerHours(
                    Number(v),
                    )
                }
            />
        </SimpleGrid>

        <Group
            justify="flex-end"
            mt="md"
        >
            <Button
                variant="default"
                onClick={onClose}
            >
                Cancel
            </Button>

            <Button
                onClick={handleSave}
                disabled={!isValid}
            >
                {product
                    ? 'Save Changes'
                    : 'Add Product'}
            </Button>
        </Group>
        </Stack>
    </Modal>
  )
}

export default AddProductModal