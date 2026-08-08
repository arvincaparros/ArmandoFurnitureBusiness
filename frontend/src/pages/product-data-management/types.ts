export interface Product {
  id: number

  productName: string

  wood: number
  epoxy: number
  nails: number
  glue: number
  sandpaper: number
  doorknob: number

  laborHours: number
  sawHours: number
  thicknessPlanerHours: number
  handPlanerHours: number

  sellingPrice: number

  materialCost: number
  laborCost: number
  machineCost: number
  totalCost: number
  profit: number
}