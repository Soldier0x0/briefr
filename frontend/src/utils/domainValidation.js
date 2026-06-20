/**
 * Validate DNS hostnames for IOC domain detection (ASCII + IDN/punycode).
 */

const IPV4_RE = /^(\d{1,3}\.){3}\d{1,3}$/
const DOMAIN_LABEL = '[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
export const DOMAIN_ASCII_RE = new RegExp(`^(?:${DOMAIN_LABEL}\\.)+${DOMAIN_LABEL}$`)

/** Global pattern for extracting ASCII/punycode domains from free text. */
export const DOMAIN_EXTRACT_RE = new RegExp(
  `\\b(?:${DOMAIN_LABEL}\\.)+(?:${DOMAIN_LABEL})\\b`,
  'gi',
)

function isIpv4(host) {
  if (!IPV4_RE.test(host)) return false
  return host.split('.').every(octet => {
    const n = Number(octet)
    return Number.isInteger(n) && n >= 0 && n <= 255
  })
}

/**
 * @param {string} host
 * @returns {boolean}
 */
export function isValidDomain(host) {
  if (!host) return false

  const trimmed = host.replace(/\.$/, '').toLowerCase()
  if (!trimmed || trimmed.length > 253) return false

  let asciiHost = trimmed
  try {
    asciiHost = new URL(`http://${trimmed}`).hostname
  } catch {
    return false
  }

  if (!asciiHost || asciiHost.length > 253) return false
  if (isIpv4(asciiHost)) return false
  return DOMAIN_ASCII_RE.test(asciiHost)
}
