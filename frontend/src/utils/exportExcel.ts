import ExcelJS from 'exceljs'

export const exportExcel = async (
  filename: string,
  rows: Record<string, unknown>[],
) => {
  if (!rows.length) return

  const workbook = new ExcelJS.Workbook()

  const worksheet = workbook.addWorksheet(
    'Transactions',
  )

  worksheet.columns = Object.keys(rows[0]).map(
    (key) => ({
      header: key,
      key,
      width: 22,
    }),
  )

  rows.forEach((row) => {
    worksheet.addRow(row)
  })

  // Make header bold
  worksheet.getRow(1).font = {
    bold: true,
  }

  const buffer =
    await workbook.xlsx.writeBuffer()

  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })

  const url = URL.createObjectURL(blob)

  const link =
    document.createElement('a')

  link.href = url
  link.download = `${filename}.xlsx`

  document.body.appendChild(link)

  link.click()

  document.body.removeChild(link)

  URL.revokeObjectURL(url)
}