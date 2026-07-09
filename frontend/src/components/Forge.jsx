import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchForgeCoverage,
  fetchHuntPack,
  fetchThreatModelScenarios,
  generateHuntPack,
  runProofBench,
} from '../api.js'
import { notifyApiError } from './Toast.jsx'
import Tooltip from './ui/Tooltip.jsx'
import { ingestLogUrl } from '../utils/adminLinks.js'
import { useAssetProfileOptional } from '../context/AssetProfileContext.jsx'
import { profileToMatchAssets } from '../utils/assetProfileIo.js'
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

function ProofBenchSection({ packs }) {
  const [selectedPackId, setSelectedPackId] = useState(packs[0]?.id ?? null)
  const [lines, setLines] = useState('')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)

  const selectedPack = useMemo(
    () => packs.find(p => p.id === selectedPackId) || packs[0],
    [packs, selectedPackId],
  )

  useEffect(() => {
    setSelectedPackId(packs[0]?.id ?? null)
    setLines('')
    setResult(null)
    setError(null)
    setErrorRequestId(null)
  }, [packs])

  const handleRun = useCallback(() => {
    const splitLines = lines.split('\n')
    if (!splitLines.some(l => l.trim())) {
      setError('Paste at least one log line')
      setErrorRequestId(null)
      return
    }
    if (!selectedPack?.sigma_yaml) {
      setError('Selected pack has no Sigma rule')
      setErrorRequestId(null)
      return
    }
    setRunning(true)
    setError(null)
    setErrorRequestId(null)
    setResult(null)
    runProofBench({ lines: splitLines, sigmaYaml: selectedPack.sigma_yaml })
      .then(setResult)
      .catch(err => {
        setError(err.message || 'Proof run failed')
        setErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
      .finally(() => setRunning(false))
  }, [lines, selectedPack])

  if (!packs.length) return null

  const hitRatePct = result ? Math.round((result.hit_rate || 0) * 100) : 0

  return (
    <section className="fg-section" aria-label="Rule proof bench">
      <div className="fg-proof-head">
        <h4 className="fg-section-label mono">RULE PROOF BENCH</h4>
        <Tooltip text="Paste sample log lines and run the pack's Sigma keywords/selection strings against them — file-based, no live SIEM. Hit rate counts lines matching any extracted pattern.">
          <span className="fg-proof-help mono" tabIndex={-1}>?</span>
        </Tooltip>
      </div>
      {packs.length > 1 && (
        <label className="fg-proof-pack-select">
          <span className="mono">PACK</span>
          <select
            className="fg-proof-select mono"
            value={selectedPack?.id ?? ''}
            onChange={e => setSelectedPackId(Number(e.target.value))}
          >
            {packs.map(pack => (
              <option key={pack.id} value={pack.id}>{pack.title}</option>
            ))}
          </select>
        </label>
      )}
      <label className="fg-proof-lines-label">
        <span className="fg-siem-label mono">LOG LINES (one per row)</span>
        <textarea
          className="fg-proof-textarea mono"
          rows={6}
          value={lines}
          onChange={e => setLines(e.target.value)}
          placeholder="// Paste nginx, auth, or app logs to test the Sigma rule…"
          spellCheck={false}
        />
      </label>
      <div className="fg-proof-actions">
        <button
          type="button"
          className="fg-generate-btn mono"
          onClick={handleRun}
          disabled={running || !lines.trim()}
        >
          {running ? 'RUNNING…' : 'RUN PROOF'}
        </button>
        {selectedPack && (
          <span className="fg-proof-pack-hint mono">{selectedPack.title}</span>
        )}
      </div>
      {error && (
        <p className="fg-error mono">
          // {error}
          {errorRequestId && (
            <>
              {' '}
              (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                ref: {errorRequestId}
              </a>)
            </>
          )}
        </p>
      )}
      {result && (
        <div className="fg-proof-result">
          <div className="fg-proof-stats mono">
            <Tooltip text="Lines in the paste that matched at least one Sigma keyword or selection string.">
              <span className="fg-proof-stat fg-proof-stat-hit">
                HITS {result.hit_count}/{result.total_lines}
              </span>
            </Tooltip>
            <Tooltip text="Non-empty lines with no pattern match in this run.">
              <span className="fg-proof-stat fg-proof-stat-miss">
                MISSES {result.miss_count}
              </span>
            </Tooltip>
            <Tooltip text="hit_count ÷ total non-empty lines.">
              <span className="fg-proof-stat">
                RATE {hitRatePct}%
              </span>
            </Tooltip>
          </div>
          {result.false_positive_hints?.length > 0 && (
            <div className="fg-proof-fp">
              <span className="fg-siem-label mono">FALSE POSITIVE HINTS</span>
              <ul className="fg-pattern-list">
                {result.false_positive_hints.map((hint, i) => (
                  <li key={i} className="fg-pattern">{hint}</li>
                ))}
              </ul>
            </div>
          )}
          {result.sample_hits?.length > 0 ? (
            <ul className="fg-proof-hit-list">
              {result.sample_hits.map(hit => (
                <li key={hit.line_number} className="fg-proof-hit">
                  <span className="fg-proof-hit-line mono">L{hit.line_number}</span>
                  <code className="fg-proof-hit-text mono">{hit.line}</code>
                  <span className="fg-proof-hit-pat mono">
                    matched: {(hit.matched_patterns || []).join(', ')}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="fg-panel-empty mono">// No hits — try different log lines or check Sigma keywords</p>
          )}
        </div>
      )}
    </section>
  )
}

function SavedPack({ pack, defaultOpen }) {
  // Freeze the initial open state: <details> stays uncontrolled, so a later
  // re-render (second pack saved flips defaultOpen) never force-toggles a
  // panel the user opened or closed. React has no defaultOpen DOM prop —
  // passing a changing `open` would re-assert it on prop diffs.
  const [initialOpen] = useState(defaultOpen)
  return (
    <details className="fg-pack" open={initialOpen || undefined}>
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
  )
}

function HuntPackPanel({ techniqueId, onPackSaved }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [generatingCve, setGeneratingCve] = useState(null)
  const [generateError, setGenerateError] = useState(null)
  const [generateErrorRequestId, setGenerateErrorRequestId] = useState(null)

  const loadHuntPack = useCallback(() => {
    if (!techniqueId) return undefined
    let cancelled = false
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    setGenerateError(null)
    setGenerateErrorRequestId(null)
    fetchHuntPack(techniqueId)
      .then(data => { if (!cancelled) setDetail(data) })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to load hunt pack')
          setErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [techniqueId])

  useEffect(() => loadHuntPack(), [loadHuntPack])

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
      .catch(err => {
        setGenerateError(err.message || 'Pack generation failed')
        setGenerateErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
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
  if (error) {
    return (
      <div className="fg-error-block">
        <p className="fg-error mono">
          // {error}
          {errorRequestId && (
            <>
              {' '}
              (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                ref: {errorRequestId}
              </a>)
            </>
          )}
        </p>
        <button type="button" className="fg-error-retry-btn mono" onClick={loadHuntPack}>
          Retry
        </button>
      </div>
    )
  }
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
        {generateError && (
          <p className="fg-error mono">
            // {generateError}
            {generateErrorRequestId && (
              <>
                {' '}
                (<a href={ingestLogUrl({ level: 'ERROR', requestId: generateErrorRequestId })}>
                  ref: {generateErrorRequestId}
                </a>)
              </>
            )}
          </p>
        )}
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
            <SavedPack key={pack.id} pack={pack} defaultOpen={packs.length === 1} />
          ))}
        </section>
      )}

      {packs.length > 0 && <ProofBenchSection packs={packs} />}

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

function ThreatScenariosPanel({
  profileStack,
  selectedTechnique,
  onSelectTechnique,
  onGeneratePack,
  generatingCve,
}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)

  useEffect(() => {
    if (!profileStack) {
      setData(null)
      return undefined
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    fetchThreatModelScenarios(profileStack)
      .then(payload => { if (!cancelled) setData(payload) })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to load threat scenarios')
          setErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [profileStack])

  if (!profileStack) {
    return (
      <p className="fg-panel-empty mono">
        // Load an asset profile to see environment threat scenarios for your stack
      </p>
    )
  }
  if (loading) return <SkeletonRows count={6} />
  if (error) {
    return (
      <div className="fg-error-block">
        <p className="fg-error mono">// {error}</p>
      </div>
    )
  }
  if (!data?.scenarios?.length) {
    return (
      <p className="fg-panel-empty mono">
        // No ATT&amp;CK techniques linked to CVEs matching your stack yet
      </p>
    )
  }

  return (
    <ul className="fg-scenario-list">
      {data.scenarios.map(scenario => (
        <li key={scenario.technique_id}>
          <article
            className={`fg-scenario-card${selectedTechnique === scenario.technique_id ? ' fg-scenario-card-active' : ''}`}
          >
            <button
              type="button"
              className="fg-scenario-head"
              onClick={() => onSelectTechnique(scenario.technique_id)}
            >
              <span className="fg-scenario-id mono">{scenario.technique_id}</span>
              <span className="fg-scenario-name">{scenario.name}</span>
              <StatusChip status={scenario.coverage_status} />
            </button>
            <p className="fg-scenario-body">{scenario.scenario}</p>
            {scenario.evidence_cves?.length > 0 && (
              <div className="fg-scenario-evidence">
                <span className="fg-section-label mono">CVE EVIDENCE</span>
                <ul className="fg-scenario-cves">
                  {scenario.evidence_cves.map(cve => (
                    <li key={cve.cve_id} className="mono">
                      {cve.cve_id}
                      {cve.is_kev && <span className="fg-kev-badge">KEV</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {scenario.mitigations?.length > 0 && (
              <div className="fg-scenario-actions">
                {scenario.mitigations.map((action, idx) => (
                  <button
                    key={`${action.type}-${action.cve_id || idx}`}
                    type="button"
                    className="admin-btn admin-btn-ghost fg-scenario-action mono"
                    disabled={action.type === 'hunt_pack' && generatingCve === action.cve_id}
                    onClick={() => {
                      if (action.type === 'hunt_pack' && action.cve_id) {
                        onGeneratePack(action.cve_id, action.technique_id)
                      } else {
                        onSelectTechnique(action.technique_id || scenario.technique_id)
                      }
                    }}
                  >
                    {action.type === 'hunt_pack' && generatingCve === action.cve_id
                      ? 'GENERATING…'
                      : action.label}
                  </button>
                ))}
              </div>
            )}
          </article>
        </li>
      ))}
    </ul>
  )
}

export default function Forge() {
  const [viewMode, setViewMode] = useState('coverage')
  const [coverage, setCoverage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [stackOnly, setStackOnly] = useState(false)
  const [selectedTechnique, setSelectedTechnique] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [generatingFromScenario, setGeneratingFromScenario] = useState(null)
  const assetCtx = useAssetProfileOptional()

  const profileStack = useMemo(() => {
    if (!assetCtx?.isLoaded || !assetCtx?.profile) return ''
    const products = profileToMatchAssets(assetCtx.profile)
      .map(a => a.product)
      .filter(Boolean)
    return [...new Set(products)].join(', ')
  }, [assetCtx?.isLoaded, assetCtx?.profile])

  useEffect(() => {
    if (!profileStack) setStackOnly(false)
  }, [profileStack])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    fetchForgeCoverage(stackOnly ? profileStack : '')
      .then(data => { if (!cancelled) setCoverage(data) })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to load coverage map')
          setErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [stackOnly, profileStack, reloadKey])

  const handleRetryCoverage = useCallback(() => setReloadKey(k => k + 1), [])

  // A saved pack flips the technique to "yours" — refetch keeps the map honest.
  const handlePackSaved = useCallback(() => {
    setReloadKey(k => k + 1)
  }, [])

  const handleScenarioGenerate = useCallback((cveId, techniqueId) => {
    setGeneratingFromScenario(cveId)
    setSelectedTechnique(techniqueId)
    generateHuntPack(cveId, techniqueId)
      .then(() => handlePackSaved())
      .catch(err => notifyApiError(err))
      .finally(() => setGeneratingFromScenario(null))
  }, [handlePackSaved])

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
          See which ATT&amp;CK techniques your feed CVEs map to, review environment threat scenarios
          for your stack, find community detection rules, and export Sigma and SIEM hunt templates per CVE.
          Rules are starting points — validate before production.
        </p>
      </header>

      <div className="fg-toolbar">
        <div className="fg-view-toggle mono" role="tablist" aria-label="Forge view">
          <button
            type="button"
            role="tab"
            className={`fg-view-btn${viewMode === 'coverage' ? ' active' : ''}`}
            aria-selected={viewMode === 'coverage'}
            onClick={() => setViewMode('coverage')}
          >
            Coverage map
          </button>
          <button
            type="button"
            role="tab"
            className={`fg-view-btn${viewMode === 'scenarios' ? ' active' : ''}`}
            aria-selected={viewMode === 'scenarios'}
            onClick={() => setViewMode('scenarios')}
          >
            Threat scenarios
          </button>
        </div>
        {counts && (
          <div className="fg-counts" role="status" aria-label="Coverage summary">
            <span className="fg-count mono"><StatusChip status="gap" /> {counts.gap}</span>
            <span className="fg-count mono"><StatusChip status="community" /> {counts.community}</span>
            <span className="fg-count mono"><StatusChip status="yours" /> {counts.yours}</span>
          </div>
        )}
        {profileStack && (
          <label className="fg-stack-toggle mono">
            <input
              type="checkbox"
              checked={stackOnly}
              onChange={e => setStackOnly(e.target.checked)}
            />
            MY STACK ONLY ({profileStack})
          </label>
        )}
      </div>

      {error && (
        <div className="fg-error-block">
          <p className="fg-error mono">
            // {error}
            {errorRequestId && (
              <>
                {' '}
                (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                  ref: {errorRequestId}
                </a>)
              </>
            )}
          </p>
          <button type="button" className="fg-error-retry-btn mono" onClick={handleRetryCoverage}>
            Retry
          </button>
        </div>
      )}

      <div className="fg-layout">
        <section className="fg-map" aria-label={viewMode === 'coverage' ? 'MITRE coverage map' : 'Threat scenarios'}>
          <h2 className="fg-section-label mono">
            {viewMode === 'coverage' ? 'COVERAGE MAP' : 'THREAT SCENARIOS'}
          </h2>
          {viewMode === 'coverage' ? (
            loading ? (
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
            )
          ) : (
            <ThreatScenariosPanel
              profileStack={profileStack}
              selectedTechnique={selectedTechnique}
              onSelectTechnique={setSelectedTechnique}
              onGeneratePack={handleScenarioGenerate}
              generatingCve={generatingFromScenario}
            />
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
