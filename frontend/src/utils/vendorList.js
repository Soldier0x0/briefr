/** Common vendor chips + search aliases (substring match on affected_products JSON). */

export const VENDORS = [
  'Microsoft', 'Linux', 'Google', 'Apple', 'Oracle',
  'Apache', 'Adobe', 'Mozilla', 'Cisco', 'IBM',
  'WordPress', 'Redhat', 'Dell', 'VMware', 'F5',
  'Fortinet', 'Ivanti', 'Citrix', 'Paloaltonetworks', 'Atlassian',
  'SAP', 'Jenkins', 'MongoDB', 'Kubernetes', 'Docker',
  'GitLab', 'Juniper', 'HP', 'Siemens', 'Python',
  'Amazon', 'Check Point', 'Node.js', 'PHP', 'Palo Alto',
]

/** Display label / phrase → search term that matches CPE slugs in affected_products. */
export const VENDOR_ALIASES = {
  'palo alto': 'paloaltonetworks',
  'palo alto networks': 'paloaltonetworks',
  'red hat': 'redhat',
  'redhat': 'redhat',
  'ms': 'microsoft',
  'msft': 'microsoft',
}

const VENDOR_LOOKUP = buildVendorLookup()

function buildVendorLookup() {
  const map = new Map()
  for (const vendor of VENDORS) {
    map.set(vendor.toLowerCase(), vendor)
  }
  for (const [alias, slug] of Object.entries(VENDOR_ALIASES)) {
    map.set(alias.toLowerCase(), slug)
  }
  return map
}

/** Resolve a token to the vendor search term (slug-friendly). */
export function resolveVendorToken(token) {
  const key = String(token || '').trim().toLowerCase()
  if (!key) return null
  if (VENDOR_LOOKUP.has(key)) {
    return VENDOR_LOOKUP.get(key)
  }
  for (const [alias, slug] of Object.entries(VENDOR_ALIASES)) {
    if (key === alias || key.includes(alias)) {
      return slug
    }
  }
  return null
}

export function isKnownVendorToken(token) {
  return resolveVendorToken(token) !== null
}
