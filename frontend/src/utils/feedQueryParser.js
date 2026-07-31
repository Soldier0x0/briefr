/**
 * Deterministic FEED search query parser (no LLM).
 * Maps analyst query strings → structured CVE list filters.
 */

import { resolveVendorToken, VENDOR_ALIASES } from './vendorList.js'

const CVE_ID_RE = /^CVE-\d{4}-\d+$/i
const TECHNIQUE_RE = /^T\d{4}(?:\.\d{3})?$/i

const KEYWORD_MAP = {
  kev: 'kev_only',
  kevs: 'kev_only',
  overdue: 'kev_overdue_only',
  'kev-overdue': 'kev_overdue_only',
  'kev_overdue': 'kev_overdue_only',
  critical: 'severity:CRITICAL',
  crit: 'severity:CRITICAL',
  high: 'severity:HIGH',
  medium: 'severity:MEDIUM',
  med: 'severity:MEDIUM',
  low: 'severity:LOW',
  poc: 'poc_only',
  patch: 'patch_only',
  patched: 'patch_only',
  watchlist: 'watchlist_only',
  pinned: 'watchlist_only',
  mine: 'watchlist_only',
}

const PREFIX_HANDLERS = {
  vendor: 'vendor',
  v: 'vendor',
  is: 'is',
  sev: 'severity',
  severity: 'severity',
  cve: 'cve',
  technique: 'technique',
  t: 'technique',
  epss: 'epss',
  stack: 'stack',
  product: 'stack',
  published: 'date',
  date: 'date',
  kev: 'is',
}

const PHRASE_ALIASES = [
  ['palo alto networks', 'paloaltonetworks'],
  ['palo alto', 'paloaltonetworks'],
  ['red hat', 'redhat'],
  ...Object.entries(VENDOR_ALIASES)
    .filter(([alias]) => alias.includes(' '))
    .map(([alias, slug]) => [alias, slug]),
]

function preprocessAliases(query) {
  let text = String(query || '')
  const seen = new Set()
  for (const [from, to] of PHRASE_ALIASES) {
    const key = from.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    text = text.replace(new RegExp(`\\b${escapeRegExp(from)}\\b`, 'gi'), to)
  }
  return text
}

const PHRASE_PATTERNS = [
  { re: /^(?:any\s+)?kevs?\s+from\s+(.+)$/i, vendorGroup: 1, kev: true },
  { re: /^(.+?)\s+kevs?$/i, vendorGroup: 1, kev: true },
  { re: /^kevs?\s+from\s+(.+)$/i, vendorGroup: 1, kev: true },
]

const EMPTY_RESULT = () => ({
  search: '',
  vendors: [],
  excludeVendors: [],
  severities: [],
  kev_only: false,
  kev_overdue_only: false,
  poc_only: false,
  patch_only: false,
  watchlist_only: false,
  epss_min: null,
  technique: '',
  published_on: '',
  stack: '',
  cve_id: '',
  chips: [],
})

function addChip(chips, type, label, value) {
  chips.push({ type, label, value })
}

function parseSeverityList(raw) {
  const parts = raw.split(',').map((s) => s.trim()).filter(Boolean)
  const out = []
  for (const part of parts) {
    const mapped = KEYWORD_MAP[part.toLowerCase()]
    if (mapped?.startsWith('severity:')) {
      out.push(mapped.split(':')[1])
    } else if (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(part.toUpperCase())) {
      out.push(part.toUpperCase())
    }
  }
  return [...new Set(out)]
}

function parseVendorList(raw) {
  return raw.split(',').map((s) => s.trim()).filter(Boolean)
}

function resolveVendors(tokens) {
  const vendors = []
  for (const token of tokens) {
    const resolved = resolveVendorToken(token)
    if (resolved) vendors.push(resolved)
  }
  return [...new Set(vendors)]
}

function parseEpssValue(raw) {
  const text = String(raw || '').trim().replace(/^>/, '')
  const num = Number.parseFloat(text)
  if (!Number.isFinite(num) || num < 0 || num > 1) return null
  return num
}

function parseDateValue(raw) {
  const text = String(raw || '').trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text
  return ''
}

function tokenize(query) {
  const tokens = []
  let i = 0
  const text = query.trim()
  while (i < text.length) {
    if (text[i] === '"') {
      const end = text.indexOf('"', i + 1)
      if (end === -1) {
        tokens.push({ kind: 'text', value: text.slice(i) })
        break
      }
      tokens.push({ kind: 'quoted', value: text.slice(i + 1, end) })
      i = end + 1
      continue
    }
    if (/\s/.test(text[i]) || text[i] === '+') {
      i += 1
      continue
    }
    let j = i
    while (j < text.length && !/\s/.test(text[j]) && text[j] !== '+') j += 1
    tokens.push({ kind: 'word', value: text.slice(i, j) })
    i = j
  }
  return tokens
}

function applyKeyword(result, keyword) {
  const mapped = KEYWORD_MAP[keyword.toLowerCase()]
  if (!mapped) return false
  if (mapped.startsWith('severity:')) {
    const sev = mapped.split(':')[1]
    if (!result.severities.includes(sev)) {
      result.severities.push(sev)
      addChip(result.chips, 'severity', sev, sev)
    }
    return true
  }
  if (mapped === 'kev_only' && !result.kev_only) {
    result.kev_only = true
    addChip(result.chips, 'kev_only', 'KEV', true)
    return true
  }
  if (mapped === 'kev_overdue_only' && !result.kev_overdue_only) {
    result.kev_overdue_only = true
    addChip(result.chips, 'kev_overdue_only', 'KEV OVERDUE', true)
    return true
  }
  if (mapped === 'poc_only' && !result.poc_only) {
    result.poc_only = true
    addChip(result.chips, 'poc_only', 'PoC', true)
    return true
  }
  if (mapped === 'patch_only' && !result.patch_only) {
    result.patch_only = true
    addChip(result.chips, 'patch_only', 'Patch', true)
    return true
  }
  if (mapped === 'watchlist_only' && !result.watchlist_only) {
    result.watchlist_only = true
    addChip(result.chips, 'watchlist_only', 'Watchlist', true)
    return true
  }
  return false
}

function applyPrefixed(result, prefix, value) {
  const key = prefix.toLowerCase()
  const handler = PREFIX_HANDLERS[key]
  if (!handler) return false

  if (handler === 'vendor') {
    const vendors = resolveVendors(parseVendorList(value))
    for (const v of vendors) {
      if (!result.vendors.includes(v)) {
        result.vendors.push(v)
        addChip(result.chips, 'vendor', v, v)
      }
    }
    return true
  }

  if (handler === 'is') {
    const flag = value.toLowerCase()
    if (flag === 'kev') {
      result.kev_only = true
      addChip(result.chips, 'kev_only', 'KEV', true)
      return true
    }
    if (flag === 'overdue' || flag === 'kev-overdue') {
      result.kev_overdue_only = true
      addChip(result.chips, 'kev_overdue_only', 'KEV OVERDUE', true)
      return true
    }
    if (flag === 'poc') {
      result.poc_only = true
      addChip(result.chips, 'poc_only', 'PoC', true)
      return true
    }
    if (flag === 'patch' || flag === 'patched') {
      result.patch_only = true
      addChip(result.chips, 'patch_only', 'Patch', true)
      return true
    }
    if (flag === 'watchlist' || flag === 'mine') {
      result.watchlist_only = true
      addChip(result.chips, 'watchlist_only', 'Watchlist', true)
      return true
    }
    return applyKeyword(result, flag)
  }

  if (handler === 'severity') {
    const severities = parseSeverityList(value)
    for (const sev of severities) {
      if (!result.severities.includes(sev)) {
        result.severities.push(sev)
        addChip(result.chips, 'severity', sev, sev)
      }
    }
    return severities.length > 0
  }

  if (handler === 'cve') {
    const id = value.trim().toUpperCase()
    if (CVE_ID_RE.test(id)) {
      result.cve_id = id
      addChip(result.chips, 'cve_id', id, id)
      return true
    }
    return false
  }

  if (handler === 'technique') {
    const tid = value.trim().toUpperCase()
    if (TECHNIQUE_RE.test(tid)) {
      result.technique = tid
      addChip(result.chips, 'technique', tid, tid)
      return true
    }
    return false
  }

  if (handler === 'epss') {
    const epss = parseEpssValue(value)
    if (epss != null) {
      result.epss_min = epss
      addChip(result.chips, 'epss_min', `EPSS ≥ ${epss}`, epss)
      return true
    }
    return false
  }

  if (handler === 'stack') {
    const terms = parseVendorList(value).join(',')
    if (terms) {
      result.stack = result.stack ? `${result.stack},${terms}` : terms
      addChip(result.chips, 'stack', `stack: ${terms}`, terms)
      return true
    }
    return false
  }

  if (handler === 'date') {
    const date = parseDateValue(value)
    if (date) {
      result.published_on = date
      addChip(result.chips, 'published_on', date, date)
      return true
    }
    return false
  }

  return false
}

function applyPhrasePatterns(result, query) {
  const trimmed = query.trim()
  if (!trimmed || trimmed.includes('+') || trimmed.startsWith('"')) {
    return false
  }
  for (const pattern of PHRASE_PATTERNS) {
    const match = trimmed.match(pattern.re)
    if (!match) continue
    const vendorRaw = String(match[pattern.vendorGroup] || '').trim()
    const vendors = resolveVendors(
      parseVendorList(vendorRaw.replace(/\s+or\s+/gi, ',')),
    )
    if (!vendors.length) continue
    if (pattern.kev) {
      result.kev_only = true
      addChip(result.chips, 'kev_only', 'KEV', true)
    }
    for (const v of vendors) {
      if (!result.vendors.includes(v)) {
        result.vendors.push(v)
        addChip(result.chips, 'vendor', v, v)
      }
    }
    return true
  }
  return false
}

function applyCommaGroup(result, group, exclude) {
  const parts = group.split(',').map((s) => s.trim()).filter(Boolean)
  if (parts.length <= 1) return false

  const vendors = resolveVendors(parts)
  if (vendors.length === parts.length) {
    for (const v of vendors) {
      if (exclude) {
        if (!result.excludeVendors.includes(v)) {
          result.excludeVendors.push(v)
          addChip(result.chips, 'exclude_vendor', `−${v}`, v)
        }
      } else if (!result.vendors.includes(v)) {
        result.vendors.push(v)
        addChip(result.chips, 'vendor', v, v)
      }
    }
    return true
  }

  const severities = parseSeverityList(group)
  if (severities.length > 1) {
    for (const sev of severities) {
      if (!result.severities.includes(sev)) {
        result.severities.push(sev)
        addChip(result.chips, 'severity', sev, sev)
      }
    }
    return true
  }

  return false
}

function applyWordToken(result, word, exclude) {
  const lower = word.toLowerCase()

  if (lower === 'not' || lower === 'without') {
    return true
  }

  if (CVE_ID_RE.test(word)) {
    result.cve_id = word.toUpperCase()
    addChip(result.chips, 'cve_id', word.toUpperCase(), word.toUpperCase())
    return true
  }

  if (TECHNIQUE_RE.test(word)) {
    result.technique = word.toUpperCase()
    addChip(result.chips, 'technique', word.toUpperCase(), word.toUpperCase())
    return true
  }

  const colon = word.indexOf(':')
  if (colon > 0) {
    const prefix = word.slice(0, colon)
    const value = word.slice(colon + 1)
    if (applyPrefixed(result, prefix, value)) return true
  }

  if (applyKeyword(result, lower)) return true

  const vendor = resolveVendorToken(word)
  if (vendor) {
    if (exclude) {
      if (!result.excludeVendors.includes(vendor)) {
        result.excludeVendors.push(vendor)
        addChip(result.chips, 'exclude_vendor', `−${vendor}`, vendor)
      }
    } else if (!result.vendors.includes(vendor)) {
      result.vendors.push(vendor)
      addChip(result.chips, 'vendor', vendor, vendor)
    }
    return true
  }

  return false
}

/**
 * Parse a FEED query string into structured filters + free-text search.
 * @param {string} input
 * @returns {ReturnType<typeof EMPTY_RESULT>}
 */
export function parseFeedQuery(input) {
  const result = EMPTY_RESULT()
  const raw = preprocessAliases(String(input || '').trim())
  if (!raw) return result

  if (applyPhrasePatterns(result, raw)) {
    return result
  }

  const freeText = []
  let pendingExclude = false
  const tokens = tokenize(raw)

  for (const token of tokens) {
    if (token.kind === 'quoted') {
      freeText.push(token.value)
      addChip(result.chips, 'search', `"${token.value}"`, token.value)
      continue
    }

    let word = token.value
    if (!word) continue

    if (word.toLowerCase() === 'not' || word.toLowerCase() === 'without') {
      pendingExclude = true
      continue
    }

    let exclude = false
    if (word.startsWith('-') && word.length > 1) {
      exclude = true
      word = word.slice(1)
    } else if (pendingExclude) {
      exclude = true
      pendingExclude = false
    }

    if (word.includes(',') && applyCommaGroup(result, word, exclude)) {
      continue
    }

    if (applyWordToken(result, word, exclude)) {
      continue
    }

    if (!exclude) {
      freeText.push(word)
    }
  }

  if (result.cve_id) {
    result.search = result.cve_id
  } else if (freeText.length) {
    result.search = freeText.join(' ')
  }

  return result
}

/** Map parser output → FEED filter patch (clears unused structured fields). */
export function parsedQueryToFilters(parsed) {
  const severity = parsed.severities.length === 1 ? parsed.severities[0] : null
  const severityList = parsed.severities.length > 1 ? parsed.severities.join(',') : ''

  return {
    search: parsed.search || '',
    vendors: parsed.vendors.join(','),
    exclude_vendors: parsed.excludeVendors.join(','),
    severity,
    severity_list: severityList,
    kev_only: parsed.kev_only,
    kev_overdue_only: parsed.kev_overdue_only,
    poc_only: parsed.poc_only,
    patch_only: parsed.patch_only,
    watchlist_only: parsed.watchlist_only,
    epss_min: parsed.epss_min,
    technique: parsed.technique || '',
    published_on: parsed.published_on || '',
    stack: parsed.stack || '',
    parsed_chips: parsed.chips,
  }
}

/** Remove one parsed chip and rebuild the query string. */
export function removeChipFromQuery(query, chip) {
  const raw = String(query || '').trim()
  if (!chip) return raw

  switch (chip.type) {
    case 'vendor':
    case 'exclude_vendor':
      return raw.replace(new RegExp(`\\b-?${escapeRegExp(chip.label.replace(/^−/, ''))}\\b`, 'gi'), '').replace(/\s+/g, ' ').trim()
    case 'kev_only':
      return raw.replace(/\bkevs?\b/gi, '').replace(/\s+/g, ' ').trim()
    case 'kev_overdue_only':
      return raw.replace(/\b(kev[- ]?overdue|overdue)\b/gi, '').replace(/\s+/g, ' ').trim()
    case 'severity':
      return raw.replace(new RegExp(`\\b${chip.value}\\b`, 'gi'), '').replace(/\s+/g, ' ').trim()
    case 'poc_only':
      return raw.replace(/\bpoc\b/gi, '').replace(/\s+/g, ' ').trim()
    case 'patch_only':
      return raw.replace(/\b(patch|patched)\b/gi, '').replace(/\s+/g, ' ').trim()
    case 'watchlist_only':
      return raw.replace(/\b(watchlist|pinned|mine)\b/gi, '').replace(/\s+/g, ' ').trim()
    case 'search':
      return raw.replace(`"${chip.value}"`, '').replace(/\s+/g, ' ').trim()
    case 'cve_id':
      return raw.replace(chip.value, '').replace(/\s+/g, ' ').trim()
    case 'technique':
      return raw.replace(chip.value, '').replace(/\s+/g, ' ').trim()
    case 'epss_min':
      return raw.replace(/epss:[^\s]+/gi, '').replace(/\s+/g, ' ').trim()
    case 'published_on':
      return raw.replace(/(date|published):[^\s]+/gi, '').replace(/\s+/g, ' ').trim()
    case 'stack':
      return raw.replace(/(stack|product):[^\s]+/gi, '').replace(/\s+/g, ' ').trim()
    default:
      return raw
  }
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Toggle a quick-filter token in the search string. */
export function toggleQueryToken(query, token) {
  const parsed = parseFeedQuery(query)
  const filters = parsedQueryToFilters(parsed)
  const lower = token.toLowerCase()

  const hasToken = (() => {
    if (lower === 'kev') return filters.kev_only
    if (lower === 'kev_overdue') return filters.kev_overdue_only
    if (lower === 'critical') return filters.severity === 'CRITICAL' || filters.severity_list.includes('CRITICAL')
    if (lower === 'high') return filters.severity === 'HIGH' || filters.severity_list.includes('HIGH')
    if (lower === 'medium') return filters.severity === 'MEDIUM' || filters.severity_list.includes('MEDIUM')
    if (lower === 'poc') return filters.poc_only
    if (lower === 'watchlist') return filters.watchlist_only
    return false
  })()

  if (hasToken) {
    const chip = parsed.chips.find((c) => {
      if (lower === 'kev') return c.type === 'kev_only'
      if (lower === 'kev_overdue') return c.type === 'kev_overdue_only'
      if (lower === 'critical') return c.type === 'severity' && c.value === 'CRITICAL'
      if (lower === 'high') return c.type === 'severity' && c.value === 'HIGH'
      if (lower === 'medium') return c.type === 'severity' && c.value === 'MEDIUM'
      if (lower === 'poc') return c.type === 'poc_only'
      if (lower === 'watchlist') return c.type === 'watchlist_only'
      return false
    })
    return removeChipFromQuery(query, chip) || query.replace(new RegExp(`\\b${token}\\b`, 'gi'), '').trim()
  }

  const q = String(query || '').trim()
  return q ? `${q} ${token}` : token
}
