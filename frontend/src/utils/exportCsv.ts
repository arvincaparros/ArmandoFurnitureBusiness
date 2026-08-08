export const exportCsv = (
  filename: string,
  rows: Record<string, unknown>[],
) => {
  if (!rows.length) return

  const headers = Object.keys(rows[0])

  const csv = [
    headers.join(','),
    ...rows.map((row) =>
      headers
        .map((header) => {
          const value = row[header] ?? ''

          return `"${String(value).replace(/"/g, '""')}"`
        })
        .join(','),
    ),
  ].join('\n')

  const blob = new Blob([csv], {
    type: 'text/csv;charset=utf-8;',
  })

  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')

  link.href = url
  link.download = `${filename}.csv`

  document.body.appendChild(link)

  link.click()

  document.body.removeChild(link)

  URL.revokeObjectURL(url)
}