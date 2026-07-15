import { useCallback, useEffect, useMemo, useState } from 'react'
import { Select } from '../ui/index.js'
import { fetchHuntPack, generateHuntPack, runProofBench } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import Tooltip from '../ui/Tooltip.jsx'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { CopyButton, SkeletonRows, StatusChip } from './shared.jsx'

const SIEM_PLATFORMS = [
  ['elastic_kql', 'Elastic KQL'],
  ['splunk_spl', 'Splunk SPL'],
  ['sentinel_kql', 'Sentinel KQL'],
  ['qradar_aql', 'QRadar AQL'],
]

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
      <span className="fg-cve-meta mono" title="CVSS = industry severity (0–10) · EPSS = 30-day exploitation probability (FIRST.org)">
        {cve.severity || '—'}
        {cve.cvss_score != null && ` · CVSS ${cve.cvss_score.toFixed(1)}`}
        {cve.epss_score != null && ` · EPSS ${(cve.epss_score * 100).toFixed(1)}%`}
      </span>
      {cve.is_kev && <span className="fg-kev-badge mono" title="CISA Known Exploited Vulnerabilities — confirmed active exploitation in the wild">KEV</span>}
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
          <Select
            className="fg-proof-select mono"
            value={selectedPack?.id != null ? String(selectedPack.id) : ''}
            onChange={(v) => setSelectedPackId(Number(v))}
            options={packs.map(pack => ({ value: String(pack.id), label: pack.title }))}
          />
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

function PackContextLine({ pack }) {
  const cwes = pack.cwe_ids || []
  if (!cwes.length && pack.epss_score == null && pack.cvss_score == null) return null
  return (
    <p
      className="fg-pack-context mono"
      title="CVSS = industry severity (0–10) · EPSS = 30-day exploitation probability (FIRST.org) · CWE = weakness class (MITRE)"
    >
      {pack.cvss_score != null && `CVSS ${pack.cvss_score.toFixed(1)}`}
      {pack.epss_score != null && `${pack.cvss_score != null ? ' · ' : ''}EPSS ${(pack.epss_score * 100).toFixed(1)}%`}
      {cwes.length > 0 && `${(pack.cvss_score != null || pack.epss_score != null) ? ' · ' : ''}${cwes.join(', ')}`}
    </p>
  )
}

function SavedPack({ pack, defaultOpen, onExportPdf, exporting }) {
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
        <PackContextLine pack={pack} />
        <div className="fg-siem-head">
          <span className="fg-siem-label mono">SIGMA RULE (experimental)</span>
          <div className="fg-pack-body-actions">
            <button
              type="button"
              className="fg-copy-btn mono"
              onClick={(e) => { e.preventDefault(); onExportPdf?.(pack) }}
              disabled={exporting}
            >
              {exporting ? 'EXPORTING…' : 'EXPORT PDF'}
            </button>
            <CopyButton text={pack.sigma_yaml} />
          </div>
        </div>
        <pre className="fg-code mono">{pack.sigma_yaml}</pre>
      </div>
    </details>
  )
}

function CaseStudiesSection({ studies }) {
  if (!studies?.length) return null
  return (
    <section className="fg-section" aria-label="Related case studies">
      <div className="fg-proof-head">
        <h4 className="fg-section-label mono">CASE STUDIES ({studies.length})</h4>
        <Tooltip text="Real-world MITRE ATLAS incidents linked to CVEs mapped to this technique — cross-referenced by shared CVE, not by ATT&CK technique ID (ATLAS uses its own AI/ML taxonomy).">
          <span className="fg-proof-help mono" tabIndex={-1}>?</span>
        </Tooltip>
      </div>
      <ul className="fg-case-study-list">
        {studies.map(study => (
          <li key={study.study_id} className="fg-case-study-item">
            <p className="fg-case-study-name">{study.name}</p>
            {study.summary && <p className="fg-case-study-summary">{study.summary}</p>}
            <p className="fg-case-study-meta mono">
              {study.target || 'AI system'}
              {study.incident_date ? ` · ${study.incident_date}` : ''}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * Persistent hunt-pack rail — mounted in every Forge view (fixes FR redesign
 * P2). Renders by technique_id, same fetch/renderer regardless of which view
 * set the selection (coverage row, scenario card, backlog item, or a
 * Library row's technique).
 */
export default function HuntPackRail({ techniqueId, onPackSaved }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [generatingCve, setGeneratingCve] = useState(null)
  const [generateError, setGenerateError] = useState(null)
  const [generateErrorRequestId, setGenerateErrorRequestId] = useState(null)
  const [exportingPackId, setExportingPackId] = useState(null)

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

  const handleExportPdf = useCallback((pack) => {
    setExportingPackId(pack.id)
    import('../../utils/huntPackPdf.js')
      .then(({ downloadHuntPackPdf }) => downloadHuntPackPdf(pack, {
        technique: detail?.technique,
        caseStudies: detail?.case_studies,
      }))
      .catch(err => notifyApiError(err))
      .finally(() => setExportingPackId(null))
  }, [detail])

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

  const { technique, status, packs, siem_queries: siemQueries, log_patterns: logPatterns, linked_cves: linkedCves, case_studies: caseStudies } = detail

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
            <SavedPack
              key={pack.id}
              pack={pack}
              defaultOpen={packs.length === 1}
              onExportPdf={handleExportPdf}
              exporting={exportingPackId === pack.id}
            />
          ))}
        </section>
      )}

      {packs.length > 0 && <ProofBenchSection packs={packs} />}

      <CaseStudiesSection studies={caseStudies} />

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
