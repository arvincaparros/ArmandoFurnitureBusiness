import ExcelJS from 'exceljs'

// sheetName defaults to 'Transactions' (its original hardcoded
// value) so the existing Transaction History caller keeps behaving
// exactly as before without passing anything new - other callers
// (e.g. Product Data Management) pass their own sheet name instead
// of getting a mislabeled "Transactions" tab in an unrelated export.
export const exportExcel = async (
  filename: string,
  rows: Record<string, unknown>[],
  sheetName: string = 'Transactions',
) => {
  if (!rows.length) return

  const workbook = new ExcelJS.Workbook()

  const worksheet = workbook.addWorksheet(
    sheetName,
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