/**
 * Analyst-friendly Excel (.xlsx) export with formatting. CSV export stays in exportCsv.js.
 * ExcelJS loads on first export via dynamic import.
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

const COLORS = {
  headerFill: 'FFD9D9D9',
  altRowFill: 'FFF5F5F5',
  severity: {
    CRITICAL: 'FF8B0000',
    HIGH: 'FFFF8C00',
    MEDIUM: 'FFFFFF00',
    LOW: 'FF90EE90',
  },
  kevYes: 'FFFF6B6B',
  patch: {
    Available: 'FF90EE90',
    'Not Available': 'FFFFA500',
    'End of Life': 'FFFF4444',
  },
}

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

function columnLetter(index) {
  let n = index
  let s = ''
  while (n > 0) {
    const rem = (n - 1) % 26
    s = String.fromCharCode(65 + rem) + s
    n = Math.floor((n - 1) / 26)
  }
  return s
}

function estimateRowHeight(text, widthChars = 50) {
  const len = (text || '').length
  if (!len) return 18
  const lines = Math.ceil(len / Math.max(12, widthChars))
  return Math.min(180, Math.max(18, lines * 14))
}

export async function buildCvesWorkbook(cves) {
  const { default: ExcelJS } = await import('exceljs')
  const workbook = new ExcelJS.Workbook()
  workbook.creator = 'BRIEFR'
  workbook.created = new Date()

  const sheet = workbook.addWorksheet('CVE Export', {
    views: [{ state: 'frozen', ySplit: 1, xSplit: 1, topLeftCell: 'B2', activeCell: 'B2' }],
  })

  const headerRow = sheet.addRow(HEADERS)
  headerRow.height = 22
  headerRow.eachCell(cell => {
    cell.font = { bold: true }
    cell.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: COLORS.headerFill },
    }
    cell.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true }
    cell.border = {
      bottom: { style: 'thin', color: { argb: 'FFB0B0B0' } },
    }
  })

  const rows = cves.map(cveToXlsxRow)
  rows.forEach((row, idx) => {
    const excelRow = sheet.addRow([
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
    ])

    const isAlt = idx % 2 === 1
    excelRow.height = estimateRowHeight(row.description, 55)

    excelRow.eachCell({ includeEmpty: true }, (cell, colNumber) => {
      const header = HEADERS[colNumber - 1]
      const hAlign = CENTER_COLS.has(header) ? 'center' : 'left'
      const vAlign = header === 'Description' ? 'top' : 'middle'

      cell.alignment = {
        vertical: vAlign,
        horizontal: hAlign,
        wrapText: header === 'Description' || header === 'References',
      }

      if (isAlt) {
        cell.fill = {
          type: 'pattern',
          pattern: 'solid',
          fgColor: { argb: COLORS.altRowFill },
        }
      }

      if (header === 'CVSS' && row.cvss != null) {
        cell.numFmt = '0.0'
      }
      if (header === 'EPSS' && row.epss != null) {
        cell.numFmt = '0.00%'
      }
      if ((header === 'Published Date' || header === 'Last Modified Date') && cell.value instanceof Date) {
        cell.numFmt = 'yyyy-mm-dd'
      }
    })
  })

  const lastCol = HEADERS.length
  const lastRow = rows.length + 1
  sheet.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: lastRow, column: lastCol },
  }

  sheet.columns.forEach((col, i) => {
    const header = HEADERS[i]
    let maxLen = header.length
    sheet.getColumn(i + 1).eachCell({ includeEmpty: false }, cell => {
      let len = 10
      if (cell.value instanceof Date) {
        len = 12
      } else if (typeof cell.value === 'number') {
        len = 8
      } else if (cell.value != null) {
        const lines = String(cell.value).split('\n')
        len = Math.max(...lines.map(l => l.length), 0)
      }
      maxLen = Math.max(maxLen, Math.min(len, header === 'Description' ? 80 : 45))
    })
    col.width = Math.min(60, Math.max(10, maxLen + 2))
  })
  sheet.getColumn(HEADERS.indexOf('Description') + 1).width = 55
  sheet.getColumn(HEADERS.indexOf('References') + 1).width = 40

  if (rows.length > 0) {
    const sevCol = columnLetter(HEADERS.indexOf('Severity') + 1)
    const kevCol = columnLetter(HEADERS.indexOf('KEV Status') + 1)
    const patchCol = columnLetter(HEADERS.indexOf('Patch Status') + 1)

    const sevRules = Object.entries(COLORS.severity).map(([sev, color]) => ({
      type: 'expression',
      formulae: [`$${sevCol}2="${sev}"`],
      style: {
        fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: color } },
      },
    }))
    sheet.addConditionalFormatting({
      ref: `${sevCol}2:${sevCol}${lastRow}`,
      rules: sevRules,
    })

    sheet.addConditionalFormatting({
      ref: `${kevCol}2:${kevCol}${lastRow}`,
      rules: [{
        type: 'expression',
        formulae: [`$${kevCol}2="Yes"`],
        style: {
          fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.kevYes } },
        },
      }],
    })

    const patchRules = Object.entries(COLORS.patch).map(([status, color]) => ({
      type: 'expression',
      formulae: [`$${patchCol}2="${status}"`],
      style: {
        fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: color } },
      },
    }))
    sheet.addConditionalFormatting({
      ref: `${patchCol}2:${patchCol}${lastRow}`,
      rules: patchRules,
    })
  }

  return workbook
}

export async function downloadCvesXlsx(cves, filename) {
  const workbook = await buildCvesWorkbook(cves)
  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
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

export function exportXlsxFilename() {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `briefr-export-${yyyy}-${mm}-${dd}.xlsx`
}
