// Pure helpers shared across DetailDrawer tabs. Split from ../DetailDrawer.jsx (Phase 4).

export function severityColor(sev) {
  const s = (sev || '').toUpperCase()
  if (s === 'CRITICAL') return 'var(--red)'
  if (s === 'HIGH')     return 'var(--amber)'
  if (s === 'MEDIUM')   return 'var(--accent)'
  if (s === 'LOW')      return 'var(--green)'
  return 'var(--text3)'
}

export function techniqueLink(tech) {
  if (tech?.url) return tech.url
  const id = tech?.id || tech?.technique_id
  if (!id) return null
  const clean = id.replace(/\./g, '/')
  return `https://attack.mitre.org/techniques/${clean}/`
}

export function truncateText(text, maxLen) {
  const t = (text || '').trim()
  if (t.length <= maxLen) return t
  return `${t.slice(0, maxLen - 1)}…`
}

export function drawerEpssBarColor(score) {
  if (score >= 0.5) return 'var(--red)'
  if (score >= 0.2) return 'var(--amber)'
  return 'var(--green)'
}

export function exploitTypeLabel(type) {
  const t = (type || '').toLowerCase()
  if (t === 'metasploit') return 'Metasploit'
  if (t === 'weaponised' || t === 'weaponized') return 'Weaponised'
  return 'PoC'
}

/** MITRE CAPEC definition page for a CAPEC-### id (CIRCL enrichment). */
export function capecHref(capecId) {
  const m = String(capecId || '').trim().match(/^(?:CAPEC-)?(\d+)$/i)
  return m ? `https://capec.mitre.org/data/definitions/${m[1]}.html` : null
}

export function capecLabel(capecId) {
  const m = String(capecId || '').trim().match(/^(?:CAPEC-)?(\d+)$/i)
  return m ? `CAPEC-${m[1]}` : String(capecId || '').trim().toUpperCase()
}

/** Flatten OSV detail API payloads into drawer table rows. */
export function flattenOsvPackageRows(osvPackages) {
  if (!Array.isArray(osvPackages)) return []
  const rows = []
  for (const entry of osvPackages) {
    for (const eco of entry?.ecosystems || []) {
      const ecosystem = eco?.ecosystem || ''
      for (const pkg of eco?.packages || []) {
        const versions = Array.isArray(pkg?.versions) ? pkg.versions : []
        const introduced = versions.map(v => v?.introduced).filter(Boolean).pop() || null
        const fixed = versions.map(v => v?.fixed).filter(Boolean)[0] || null
        const rangeParts = []
        if (introduced) rangeParts.push(`>=${introduced}`)
        if (fixed) rangeParts.push(`<${fixed}`)
        rows.push({
          key: `${ecosystem}:${pkg?.name || 'unknown'}`,
          ecosystem: ecosystem || '—',
          name: pkg?.name || '—',
          range: rangeParts.length ? rangeParts.join(', ') : '—',
          fix: fixed,
        })
      }
    }
  }
  return rows
}
