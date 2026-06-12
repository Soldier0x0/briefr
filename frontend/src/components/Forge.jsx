import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchForgeCoverage,
  fetchHuntPack,
  generateHuntPack,
} from '../api.js'
import { getSavedStack } from '../utils/cveFilters.js'
import './Forge.css'

const STATUS_LABELS = {
  yours: 'YOURS',
  community: 'COMMUNITY',
  gap: 'GAP',
}

const SIEM_PLATFORMS = [
  ['elastic_kql', 'Elastic KQL'],
  ['splunk_spl', 'Splunk SPL'],
  ['sentinel_kql', 'Sentinel KQL'],
  ['qradar_aql', 'QRadar AQL'],
]

function StatusChip({ status }) {
  return (
    <span className={`fg-status-chip fg-status-${status} mono`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

function CopyButton({ text, label = 'COPY' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    if (!navigator.clipboard?.writeText) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {})
  }, [text])

  return (
    <button type="button" className="fg-copy-btn mono" onClick={handleCopy}>
      {copied ? 'COPIED ✓' : label}
    </button>
  )
}

function SkeletonRows({ count = 8 }) {
  return (
    <ul className="fg-skeleton-list" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="fg-skeleton-row" />
      ))}
    </ul>
  )
}

function CoverageRow({ technique, active, onSelect }) {
  return (
    <li>
      <button
        type="button"
        className={`fg-tech-row${active ? ' fg-tech-row-active' : ''}`}
        onClick={() => onSelect(technique.technique_id)}
        aria-pressed={active}
      >
        <span className="fg-tech-id mono">{technique.technique_id}</span>
        <span className="fg-tech-name">{technique.name || technique.technique_id}</span>
        <span className="fg-tech-counts mono">
          {technique.cve_count} CVE{technique.cve_count === 1 ? '' : 's'}
          {technique.kev_count > 0 && (
            <span className="fg-kev-count"> · {technique.kev_count} KEV</span>
          )}
        </span>
        <StatusChip status={technique.status} />
      </button>
    </li>
  )
}

function SiemQueryBlock({ platform, label, entry }) {
  if (!entry?.query) return null
  return (
    <div className="fg-siem-block" key={platform}>
      <div className="fg-siem-head">
        <span className="fg-siem-label mono">{label}</span>
        <CopyButton text={entry.query} />
      </div>
      <pre className="fg-code mono">{entry.query}</pre>
      {entry.notes && <p className="fg-siem-notes">{entry.notes}</p>}
    </div>
  )
}

function LinkedCveRow({ cve, pack, generating, onGenerate }) {
  return (
    <li className="fg-cve-row">
      <span className="fg-cve-id mono">{cve.cve_id}</span>
      <span className="fg-cve-meta mono">
        {cve.severity || '—'}
        {cve.cvss_score != null && ` · CVSS ${cve.cvss_score.toFixed(1)}`}
        {cve.epss_score != null && ` · EPSS ${(cve.epss_score * 100).toFixed(1)}%`}
      </span>
      {cve.is_kev && <span className="fg-kev-badge mono">KEV</span>}
      {pack ? (
        <span className="fg-pack-saved mono">PACK SAVED ✓</span>
      ) : (
        <button
          type="button"
          className="fg-generate-btn mono"
          onClick={() => onGenerate(cve.cve_id)}
          disabled={generating}
        >
          {generating ? 'GENERATING…' : 'GENERATE PACK'}
        </button>
      )}
    </li>
  )
}

function HuntPackPanel({ techniqueId, onPackSaved }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generatingCve, setGeneratingCve] = useState(null)
  const [generateError, setGenerateError] = useState(null)

  useEffect(() => {
    if (!techniqueId) return undefined
    let cancelled = false
    setLoading(true)
    setError(null)
    setGenerateError(null)
    fetchHuntPack(techniqueId)
      .then(data => { if (!cancelled) setDetail(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to load hunt pack') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [techniqueId])

  const packsByCve = useMemo(() => {
    const map = {}
    for (const pack of detail?.packs || []) map[pack.cve_id] = pack
    return map
  }, [detail])

  const handleGenerate = useCallback((cveId) => {
    setGeneratingCve(cveId)
    setGenerateError(null)
    generateHuntPack(cveId, techniqueId)
      .then(({ pack }) => {
        setDetail(prev => {
          if (!prev) return prev
          const rest = (prev.packs || []).filter(p => p.id !== pack.id)
          return { ...prev, status: 'yours', packs: [pack, ...rest] }
        })
        onPackSaved?.(techniqueId)
      })
      .catch(err => setGenerateError(err.message || 'Pack generation failed'))
      .finally(() => setGeneratingCve(null))
  }, [techniqueId, onPackSaved])

  if (!techniqueId) {
    return (
      <p className="fg-panel-empty mono">
        // Select a technique on the coverage map to open its hunt pack
      </p>
    )
  }
  if (loading) return <SkeletonRows count={5} />
  if (error) return <p className="fg-error mono">// {error}</p>
  if (!detail) return null

  const { technique, status, packs, siem_queries: siemQueries, log_patterns: logPatterns, linked_cves: linkedCves } = detail

  return (
    <div className="fg-panel">
      <div className="fg-panel-head">
        <div>
          <h3 className="fg-panel-title">
            <span className="mono">{technique.technique_id}</span> {technique.name}
          </h3>
          {technique.tactic && (
            <p className="fg-panel-tactic mono">{technique.tactic}</p>
          )}
        </div>
        <StatusChip status={status} />
      </div>

      {technique.description && (
        <p className="fg-panel-desc">{technique.description}</p>
      )}
      {technique.url && (
        <a className="fg-attack-link mono" href={technique.url} target="_blank" rel="noopener noreferrer">
          View on MITRE ATT&amp;CK ↗
        </a>
      )}

      <section className="fg-section" aria-label="Linked CVEs">
        <h4 className="fg-section-label mono">LINKED CVES</h4>
        {generateError && <p className="fg-error mono">// {generateError}</p>}
        {linkedCves.length === 0 ? (
          <p className="fg-panel-empty mono">// No CVEs mapped to this technique yet</p>
        ) : (
          <ul className="fg-cve-list">
            {linkedCves.map(cve => (
              <LinkedCveRow
                key={cve.cve_id}
                cve={cve}
                pack={packsByCve[cve.cve_id]}
                generating={generatingCve === cve.cve_id}
                onGenerate={handleGenerate}
              />
            ))}
          </ul>
        )}
      </section>

      {packs.length > 0 && (
        <section className="fg-section" aria-label="Saved hunt packs">
          <h4 className="fg-section-label mono">YOUR PACKS ({packs.length})</h4>
          {packs.map(pack => (
            <details key={pack.id} className="fg-pack" open={packs.length === 1}>
              <summary className="fg-pack-summary">
                <span className="fg-pack-title">{pack.title}</span>
                <span className={`fg-priority fg-priority-${pack.priority} mono`}>
                  {pack.priority.toUpperCase()}
                </span>
              </summary>
              <div className="fg-pack-body">
                <div className="fg-siem-head">
                  <span className="fg-siem-label mono">SIGMA RULE (experimental)</span>
                  <CopyButton text={pack.sigma_yaml} />
                </div>
                <pre className="fg-code mono">{pack.sigma_yaml}</pre>
              </div>
            </details>
          ))}
        </section>
      )}

      <section className="fg-section" aria-label="SIEM quick-search queries">
        <h4 className="fg-section-label mono">SIEM QUICK SEARCHES</h4>
        {SIEM_PLATFORMS.map(([platform, label]) => (
          <SiemQueryBlock
            key={platform}
            platform={platform}
            label={label}
            entry={siemQueries?.[platform]}
          />
        ))}
      </section>

      {logPatterns?.length > 0 && (
        <section className="fg-section" aria-label="What to look for in logs">
          <h4 className="fg-section-label mono">LOG PATTERNS</h4>
          <ul className="fg-pattern-list">
            {logPatterns.map((pattern, i) => (
              <li key={i} className="fg-pattern">{pattern}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export default function Forge() {
  const [coverage, setCoverage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [stackOnly, setStackOnly] = useState(false)
  const [selectedTechnique, setSelectedTechnique] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const savedStack = getSavedStack()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchForgeCoverage(stackOnly ? savedStack : '')
      .then(data => { if (!cancelled) setCoverage(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to load coverage map') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [stackOnly, savedStack, reloadKey])

  // A saved pack flips the technique to "yours" — refetch keeps the map honest.
  const handlePackSaved = useCallback(() => {
    setReloadKey(k => k + 1)
  }, [])

  const byTactic = useMemo(() => {
    const groups = new Map()
    for (const technique of coverage?.techniques || []) {
      const tactic = technique.tactic || 'Uncategorized'
      if (!groups.has(tactic)) groups.set(tactic, [])
      groups.get(tactic).push(technique)
    }
    return Array.from(groups.entries())
  }, [coverage])

  const counts = coverage?.meta?.counts

  return (
    <div className="forge" role="region" aria-label="Forge detection engineering">
      <header className="fg-hero">
        <p className="fg-hero-kicker mono">DETECTION ENGINEERING</p>
        <h1 className="fg-hero-title">Forge</h1>
        <p className="fg-hero-sub">
          MITRE ATT&amp;CK coverage for the CVEs in your intel feed — see where
          detection content exists, where it does not, and generate Sigma + SIEM
          hunt packs per CVE. Rules are templates: validate before deploying.
        </p>
      </header>

      <div className="fg-toolbar">
        {counts && (
          <div className="fg-counts" role="status" aria-label="Coverage summary">
            <span className="fg-count mono"><StatusChip status="gap" /> {counts.gap}</span>
            <span className="fg-count mono"><StatusChip status="community" /> {counts.community}</span>
            <span className="fg-count mono"><StatusChip status="yours" /> {counts.yours}</span>
          </div>
        )}
        {savedStack && (
          <label className="fg-stack-toggle mono">
            <input
              type="checkbox"
              checked={stackOnly}
              onChange={e => setStackOnly(e.target.checked)}
            />
            MY STACK ONLY ({savedStack})
          </label>
        )}
      </div>

      {error && <p className="fg-error mono">// {error}</p>}

      <div className="fg-layout">
        <section className="fg-map" aria-label="MITRE coverage map">
          <h2 className="fg-section-label mono">COVERAGE MAP</h2>
          {loading ? (
            <SkeletonRows count={10} />
          ) : byTactic.length === 0 ? (
            <p className="fg-panel-empty mono">
              {stackOnly
                ? '// No techniques linked to CVEs matching your stack'
                : '// No techniques mapped yet — wait for the MITRE feed to populate'}
            </p>
          ) : (
            byTactic.map(([tactic, techniques]) => (
              <div key={tactic} className="fg-tactic-group">
                <h3 className="fg-tactic-label mono">{tactic.toUpperCase()}</h3>
                <ul className="fg-tech-list">
                  {techniques.map(technique => (
                    <CoverageRow
                      key={technique.technique_id}
                      technique={technique}
                      active={selectedTechnique === technique.technique_id}
                      onSelect={setSelectedTechnique}
                    />
                  ))}
                </ul>
              </div>
            ))
          )}
        </section>

        <aside className="fg-detail" aria-label="Hunt pack detail">
          <h2 className="fg-section-label mono">HUNT PACK</h2>
          <HuntPackPanel
            techniqueId={selectedTechnique}
            onPackSaved={handlePackSaved}
          />
        </aside>
      </div>
    </div>
  )
}
