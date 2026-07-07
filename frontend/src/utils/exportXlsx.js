/**
 * Analyst-friendly Excel (.xlsx) export with formatting.
 * CSV export stays in exportCsv.js — separate button, plain text for integrations.
 * write-excel-file (sync zip) loads on first XLSX export via dynamic import.
 */

const HEADERS = [
  'CVE ID',
  'Severity',
  'CVSS',
  'EPSS',
  'KEV Status',
  'Published Date',
  'Last Modified Date',
  'Product',
  'Vendor',
  'Description',
  'References',
  'Affected Technology',
  'Patch Status',
]

const CENTER_COLS = new Set([
  'CVE ID',
  'Severity',
  'CVSS',
  'EPSS',
  'KEV Status',
  'Published Date',
  'Last Modified Date',
  'Patch Status',
])

const WRAP_COLS = new Set(['Description', 'References'])

const COLORS = {
  headerFill: '#d9d9d9',
  altRowFill: '#f5f5f5',
  headerBorder: '#b0b0b0',
  severity: {
    CRITICAL: '#8b0000',
    HIGH: '#ff8c00',
    MEDIUM: '#ffff00',
    LOW: '#90ee90',
  },
  kevYes: '#ff6b6b',
  patch: {
    Available: '#90ee90',
    'Not Available': '#ffa500',
    'End of Life': '#ff4444',
  },
}

const COLUMN_WIDTHS = [
  14, 12, 8, 10, 12, 14, 16, 28, 20, 55, 40, 28, 14,
]

function parseProducts(products) {
  const vendors = new Set()
  const names = []
  for (const raw of products || []) {
    const p = String(raw).trim()
    if (!p) continue
    const idx = p.indexOf(':')
    if (idx > 0) {
      vendors.add(p.slice(0, idx))
      names.push(p.slice(idx + 1))
    } else {
      names.push(p)
    }
  }
  return {
    vendor: [...vendors].join('; '),
    product: names.join('; '),
    affectedTechnology: names.join('; '),
  }
}

function formatReferences(urls) {
  if (!Array.isArray(urls) || !urls.length) return ''
  return urls.join('\n')
}

function detectPatchStatus(cve) {
  const blob = `${cve.description || ''} ${cve.summary || ''}`.toLowerCase()
  if (/\b(end of life|end-of-life|\beol\b)\b/.test(blob)) {
    return 'End of Life'
  }
  if (cve.patch_available) return 'Available'
  return 'Not Available'
}

function parseExcelDate(iso) {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) {
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/)
    if (m) return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]))
    return null
  }
  return d
}

export function cveToXlsxRow(cve) {
  const { vendor, product, affectedTechnology } = parseProducts(cve.affected_products)
  return {
    cveId: cve.cve_id ?? '',
    severity: (cve.severity || '').toUpperCase(),
    cvss: cve.cvss_score != null ? Number(cve.cvss_score) : null,
    epss: cve.epss_score != null ? Number(cve.epss_score) : null,
    kevStatus: cve.is_kev ? 'Yes' : 'No',
    published: parseExcelDate(cve.published),
    modified: parseExcelDate(cve.modified || cve.updated_at),
    product,
    vendor,
    description: cve.description ?? '',
    references: formatReferences(cve.source_urls),
    affectedTechnology,
    patchStatus: detectPatchStatus(cve),
  }
}

function headerCell(value) {
  return {
    value,
    fontWeight: 'bold',
    backgroundColor: COLORS.headerFill,
    align: 'center',
    alignVertical: 'center',
    wrap: true,
    bottomBorderColor: COLORS.headerBorder,
    bottomBorderStyle: 'thin',
  }
}

function dataCell(header, value, row, isAltRow) {
  const opts = {
    align: CENTER_COLS.has(header) ? 'center' : 'left',
    alignVertical: header === 'Description' ? 'top' : 'center',
    wrap: WRAP_COLS.has(header),
  }

  if (isAltRow) {
    opts.backgroundColor = COLORS.altRowFill
  }

  if (header === 'Severity' && COLORS.severity[row.severity]) {
    opts.backgroundColor = COLORS.severity[row.severity]
  }
  if (header === 'KEV Status' && row.kevStatus === 'Yes') {
    opts.backgroundColor = COLORS.kevYes
  }
  if (header === 'Patch Status' && COLORS.patch[row.patchStatus]) {
    opts.backgroundColor = COLORS.patch[row.patchStatus]
  }

  if (header === 'CVSS' && row.cvss != null) {
    return { ...opts, value: row.cvss, type: Number, format: '0.0' }
  }
  if (header === 'EPSS' && row.epss != null) {
    return { ...opts, value: row.epss, type: Number, format: '0.00%' }
  }
  if ((header === 'Published Date' || header === 'Last Modified Date') && value instanceof Date) {
    return { ...opts, value, type: Date, format: 'yyyy-mm-dd' }
  }

  if (value == null || value === '') {
    return Object.keys(opts).length ? { ...opts, value: null } : null
  }

  return { ...opts, value }
}

export function buildCvesSheetData(cves) {
  const rows = cves.map(cveToXlsxRow)
  const data = [
    HEADERS.map(headerCell),
    ...rows.map((row, idx) => {
      const values = [
        row.cveId,
        row.severity,
        row.cvss,
        row.epss,
        row.kevStatus,
        row.published,
        row.modified,
        row.product,
        row.vendor,
        row.description,
        row.references,
        row.affectedTechnology,
        row.patchStatus,
      ]
      return values.map((value, colIdx) => dataCell(HEADERS[colIdx], value, row, idx % 2 === 1))
    }),
  ]

  return {
    data,
    sheet: 'CVE Export',
    columns: COLUMN_WIDTHS.map(width => ({ width })),
    stickyRowsCount: 1,
    stickyColumnsCount: 1,
    dateFormat: 'yyyy-mm-dd',
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  window.setTimeout(() => {
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, 200)
}

export async function downloadCvesXlsx(cves, filename) {
  // write-excel-file/browser uses fflate's async zip() with Web Workers (blob: URLs).
  // That promise can hang indefinitely in production static bundles — use sync zip instead.
  const [
    { generateXlsxFileSync },
    { default: convertFileContentToUint8Array },
  ] = await Promise.all([
    import('write-excel-file/modules/export/writeXlsxFileUniversal.js'),
    import('write-excel-file/modules/export/convertFileContentToUint8ArrayUniversal.js'),
  ])

  const sheet = buildCvesSheetData(cves)
  const { data, ...options } = sheet
  const blob = await generateXlsxFileSync(data, options, undefined, convertFileContentToUint8Array)
  downloadBlob(blob, filename)
}

export function exportXlsxFilename() {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `briefr-export-${yyyy}-${mm}-${dd}.xlsx`
}
