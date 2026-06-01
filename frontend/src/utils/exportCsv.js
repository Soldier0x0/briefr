function escapeCsvField(value) {
  if (value == null) return ''
  const str = String(value)
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

function formatProducts(products) {
  if (!Array.isArray(products) || !products.length) return ''
  return products.join('; ')
}

export function cvesToCsvRows(cves) {
  const header = [
    'CVE ID',
    'Severity',
    'CVSS Score',
    'EPSS Score',
    'KEV',
    'Patch Available',
    'Published Date',
    'Affected Products',
    'Description',
    'MITRE Technique',
  ]

  const rows = cves.map(cve => [
    cve.cve_id ?? '',
    cve.severity ?? '',
    cve.cvss_score != null ? cve.cvss_score : '',
    cve.epss_score != null ? cve.epss_score : '',
    cve.is_kev ? 'Yes' : 'No',
    cve.patch_available ? 'Yes' : 'No',
    cve.published ?? '',
    formatProducts(cve.affected_products),
    cve.description ?? '',
    cve.mitre_technique ?? '',
  ])

  return [header, ...rows]
    .map(row => row.map(escapeCsvField).join(','))
    .join('\n')
}

export function downloadCsv(csv, filename) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function exportFilename() {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `briefr-export-${yyyy}-${mm}-${dd}.csv`
}
