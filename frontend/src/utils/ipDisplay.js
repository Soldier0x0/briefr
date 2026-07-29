const IPV4_RE =
  /^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d?\d)){3})$/

const IPV4_MAPPED_RE =
  /^::ffff:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/i

/**
 * Split a rate-limit client key into IPv4 and IPv6 display strings.
 * Supports plain IPv4, IPv6, and IPv4-mapped IPv6 (::ffff:x.x.x.x).
 *
 * @param {string} raw
 * @returns {{ ipv4: string, ipv6: string }}
 */
export function formatClientAddresses(raw) {
  const key = String(raw || '').trim()
  if (!key) return { ipv4: 'N/A', ipv6: 'N/A' }

  const mapped = key.match(IPV4_MAPPED_RE)
  if (mapped) {
    return { ipv4: mapped[1], ipv6: 'N/A' }
  }

  if (IPV4_RE.test(key)) {
    return { ipv4: key, ipv6: 'N/A' }
  }

  if (key.includes(':')) {
    return { ipv4: 'N/A', ipv6: key }
  }

  return { ipv4: key, ipv6: 'N/A' }
}

export function formatClientAddressLabel(raw) {
  const { ipv4, ipv6 } = formatClientAddresses(raw)
  if (ipv4 !== 'N/A' && ipv6 !== 'N/A') {
    return `IPv4 ${ipv4} · IPv6 ${ipv6}`
  }
  if (ipv4 !== 'N/A') return `IPv4 ${ipv4}`
  if (ipv6 !== 'N/A') return `IPv6 ${ipv6}`
  return 'N/A'
}
