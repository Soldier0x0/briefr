import { useState, useRef, useEffect, useCallback } from 'react'
import { lookupIOC, fetchIocWatchlist, addIocWatchlist, removeIocWatchlist } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import { ingestLogUrl } from '../utils/adminLinks.js'
import { useInvestigationOptional } from '../context/InvestigationContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { isValidDomain } from '../utils/domainValidation.js'
import { IOC_NOT_FOUND_IN_DATABASES } from '../utils/iocLookupMessages.js'
import { formatSectionHeading } from '../utils/sectionHeading.js'
import { Checkbox } from './ui/index.js'
import { DOMAIN_TERM_TIPS } from '../utils/domainTermTips.js'
import './IOCLookup.css'

import IOCQuotaPanel from './ioc/IOCQuotaPanel.jsx'
import {
  ActionRow,
  DetailGrid,
  EnrichmentBlock,
  HistoryItem,
  IdleLookupState,
  IPResultBody,
  OtxEnrichment,
  ThreatBar,
  WatchlistPanel,
} from './ioc/IOCResultComponents.jsx'
import {
  TYPE_LABELS,
  detectType,
  normalizeIocValue,
  parseError,
  verdictInfo,
} from './ioc/iocUtils.js'

// ── Main component ────────────────────────────────────────
export default function IOCLookup({ prefill }) {
  const investigation = useInvestigationOptional()
  const { status: authStatus } = useAuth()
  const authed = authStatus === 'authed'
  const [value, setValue]       = useState('')
  const [detectedType, setDetectedType] = useState(null)
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [copied, setCopied]     = useState(false)
  const [history, setHistory]   = useState([])   // session-only, no localStorage
  const [includeGreynoise, setIncludeGreynoise] = useState(false)
  const [watchlistItems, setWatchlistItems] = useState([])
  const [watchlistLoading, setWatchlistLoading] = useState(false)
  const [watchlistError, setWatchlistError] = useState(null)
  const [watchlistErrorRequestId, setWatchlistErrorRequestId] = useState(null)
  const [watchlistSaving, setWatchlistSaving] = useState(false)
  const [watchlistRemovingId, setWatchlistRemovingId] = useState(null)

  const detectDebounce = useRef(null)
  const copiedTimerRef = useRef(null)

  useEffect(() => () => {
    if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current)
  }, [])
  const prefillHandled = useRef(null)
  const [indicatorQueue, setIndicatorQueue] = useState([])
  const [fromCveId, setFromCveId] = useState(null)
  const pivotFromRef = useRef(null)

  const applyDetection = useCallback((val) => {
    const t = detectType(val)
    setDetectedType(t)
    return t
  }, [])

  // Auto-detect type after 300ms pause (paste triggers immediate detect)
  const handleValueChange = useCallback((e) => {
    const val = e.target.value
    setValue(val)
    if (detectDebounce.current) clearTimeout(detectDebounce.current)
    detectDebounce.current = setTimeout(() => {
      applyDetection(val)
    }, 300)
  }, [applyDetection])

  const handlePaste = useCallback((e) => {
    const pasted = e.clipboardData?.getData('text') || ''
    const next = `${value}${pasted}`
    setTimeout(() => applyDetection(next), 0)
  }, [value, applyDetection])

  // Clean up debounce on unmount
  useEffect(() => () => {
    if (detectDebounce.current) clearTimeout(detectDebounce.current)
  }, [])

  const loadWatchlist = useCallback(() => {
    if (!authed) {
      setWatchlistItems([])
      return undefined
    }
    setWatchlistLoading(true)
    setWatchlistError(null)
    setWatchlistErrorRequestId(null)
    return fetchIocWatchlist()
      .then(data => setWatchlistItems(data.items || []))
      .catch(err => {
        setWatchlistError(err.message || 'Failed to load IOC watchlist')
        setWatchlistErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
      .finally(() => setWatchlistLoading(false))
  }, [authed])

  useEffect(() => {
    loadWatchlist()
  }, [loadWatchlist])

  const watchlistSaved = result && watchlistItems.some(
    item => item.ioc_type === result.type && item.ioc_value === result.value,
  )

  const handleSaveWatchlist = useCallback(() => {
    if (!result?.value || !result?.type || !authed) return
    setWatchlistSaving(true)
    addIocWatchlist({ value: result.value, type: result.type })
      .then(() => loadWatchlist())
      .catch(err => notifyApiError(err))
      .finally(() => setWatchlistSaving(false))
  }, [result, authed, loadWatchlist])

  const handleRemoveWatchlist = useCallback((entryId) => {
    setWatchlistRemovingId(entryId)
    removeIocWatchlist(entryId)
      .then(() => loadWatchlist())
      .catch(err => notifyApiError(err))
      .finally(() => setWatchlistRemovingId(null))
  }, [loadWatchlist])

  async function runLookup(lookupValue, lookupType, options = {}) {
    const raw = (lookupValue ?? value).trim()
    const type = lookupType ?? detectedType ?? detectType(raw)
    if (!raw) return
    if (!type) {
      setError('Unrecognized indicator — paste an IPv4 address, file hash (MD5/SHA1/SHA256), or domain/URL.')
      setErrorRequestId(null)
      return
    }
    const trimmed = normalizeIocValue(raw, type)

    if (type === 'domain' && !isValidDomain(trimmed)) {
      setLoading(false)
      setResult(null)
      setError(
        `'${raw}' is not a valid domain. Paste a full hostname (e.g. plugins.trac.wordpress.org) or URL — filenames like class-query.php cannot be looked up.`,
      )
      setErrorRequestId(null)
      return
    }

    setLoading(true)
    setResult(null)
    setError(null)
    setErrorRequestId(null)

    try {
      const useGreynoise = type === 'ip' && (options.greynoise ?? includeGreynoise)
      const data = await lookupIOC(trimmed, type, { greynoise: useGreynoise })

      // Surface backend-level auth/not-found errors
      if (data.error) {
        const msg = data.error.toLowerCase()
        if (msg.includes('auth') || msg.includes('key')) {
          setError('Threat-intelligence API key missing or invalid on this server. Ask your administrator.')
        } else if (msg.includes('not found') || msg.includes('404')) {
          setError(IOC_NOT_FOUND_IN_DATABASES)
        } else {
          // Show result even if there's a partial error
          setResult(data)
        }
      } else {
        setResult(data)
      }

      if (investigation?.isActive && !data.error) {
        investigation.recordIocPivot(trimmed, options.pivotFrom ?? pivotFromRef.current)
      }

      // Add to session history (deduplicate by value, cap at 5)
      const verdict = verdictInfo(data.malicious_votes, data.total_votes)
      setHistory(prev => {
        const filtered = prev.filter(h => h.value !== trimmed)
        return [
          {
            value: trimmed,
            iocType: type,
            malicious: data.malicious_votes ?? 0,
            total: data.total_votes ?? 0,
            verdict: verdict.label,
          },
          ...filtered,
        ].slice(0, 5)
      })
    } catch (err) {
      setError(parseError(err))
      setErrorRequestId(err?.requestId || null)
      notifyApiError(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!prefill?.trigger) return
    if (prefillHandled.current === prefill.trigger) return
    prefillHandled.current = prefill.trigger

    const indicators = Array.isArray(prefill.indicators) && prefill.indicators.length
      ? prefill.indicators
      : prefill.value
        ? [{ type: 'ip', value: prefill.value }]
        : []

    setFromCveId(prefill.fromCveId || null)
    pivotFromRef.current = prefill.pivotFrom || null
    setIndicatorQueue(indicators)

    const first = indicators[0]
    if (!first?.value) return

    setValue(first.value)
    const t = first.type === 'domain' ? 'domain' : first.type === 'hash' ? 'hash' : 'ip'
    setDetectedType(t)
    // Analyst reviews chips first; prefill input only (no auto-lookup blast)
  }, [prefill?.trigger, prefill?.value, prefill?.indicators, prefill?.fromCveId, prefill?.pivotFrom])

  function selectQueuedIndicator(ind) {
    if (!ind?.value) return
    const t = ind.type === 'domain' ? 'domain' : ind.type === 'hash' ? 'hash' : 'ip'
    setValue(ind.value)
    setDetectedType(t)
  }

  function clearLookup() {
    setValue('')
    setDetectedType(null)
    setResult(null)
    setError(null)
    setCopied(false)
    setIndicatorQueue([])
    setFromCveId(null)
    pivotFromRef.current = null
    prefillHandled.current = null
  }

  const hasLookupState = !!(
    value.trim() ||
    result ||
    error ||
    indicatorQueue.length ||
    fromCveId
  )

  function handleKeyDown(e) {
    if (e.key === 'Enter') runLookup()
  }

  function handleRerun(item) {
    setValue(item.value)
    const t = item.iocType || detectType(item.value)
    setDetectedType(t)
    runLookup(item.value, t)
  }

  async function copyReport() {
    if (!result) return
    const { label } = verdictInfo(result.malicious_votes, result.total_votes)
    const tags = (result.tags || []).join(', ') || 'none'
    const lines = [
      'IOC Report — BRIEFR',
      `Type:    ${result.type?.toUpperCase()}`,
      `Value:   ${result.value}`,
      `Verdict: ${label.toUpperCase()}`,
      `Score:   ${result.malicious_votes ?? 0} / ${result.total_votes ?? 0} engines flagged`,
      result.country    ? `Country: ${result.country}` : null,
      result.abuse_score != null ? `Abuse:   ${result.abuse_score} / 100` : null,
      result.abuseipdb?.isp ? `ISP:     ${result.abuseipdb.isp}` : null,
      result.abuseipdb?.total_reports != null
        ? `Reports: ${result.abuseipdb.total_reports}`
        : null,
      `Tags:    ${tags}`,
      result.vt_link    ? `Report:  ${result.vt_link}` : null,
      result.greynoise_sentence ? `GreyNoise: ${result.greynoise_sentence}` : null,
      result.malwarebazaar_sentence ? `MalwareBazaar: ${result.malwarebazaar_sentence}` : null,
      result.urlhaus_sentence ? `URLhaus: ${result.urlhaus_sentence}` : null,
      '',
      'Source: BRIEFR — VirusTotal, AbuseIPDB, GreyNoise, MalwareBazaar, URLhaus',
    ].filter(l => l !== null).join('\n')

    try {
      await navigator.clipboard.writeText(lines)
      setCopied(true)
      if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current)
      copiedTimerRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard may be unavailable in some browser contexts
    }
  }

  const hasResult = !!result && !error

  return (
    <section className="ioc-lookup" aria-label="IOC threat intelligence lookup">

      {/* ── Page header ── */}
      <div className="ioc-page-header">
        <h1 className="ioc-page-title">IOC LOOKUP</h1>
        <p className="ioc-page-sub">
          Check whether an IP, file hash, or domain appears in threat feeds. Paste a full URL or hostname — not filenames.
          GreyNoise is optional — per lookup when you opt in (50 calls/week shared quota).
        </p>
      </div>

      {fromCveId && (
        <div className="ioc-from-cve-banner mono" role="status">
          Indicators suggested from <span className="ioc-from-cve-id">{fromCveId}</span>
          — select a chip, then run LOOKUP when ready.
        </div>
      )}

      {indicatorQueue.length > 0 && (
        <div className="ioc-indicator-queue" role="group" aria-label="Suggested indicators">
          {indicatorQueue.map(ind => (
            <button
              key={`${ind.type}:${ind.value}`}
              type="button"
              className={`ioc-indicator-chip mono${value.trim() === ind.value ? ' selected' : ''}`}
              onClick={() => selectQueuedIndicator(ind)}
              aria-pressed={value.trim() === ind.value}
            >
              <span className="ioc-chip-type">{ind.type.toUpperCase()}</span>
              {ind.value}
            </button>
          ))}
        </div>
      )}

      {/* ── Input section ── */}
      <div className="ioc-input-section">
        <label htmlFor="ioc-value-input" className="ioc-input-label">
          {formatSectionHeading('// INDICATOR')}
        </label>
        <div className="ioc-search-row">
          <textarea
            id="ioc-value-input"
            className="ioc-value-input ioc-search-input mono"
            value={value}
            onChange={handleValueChange}
            onPaste={handlePaste}
            onKeyDown={handleKeyDown}
            placeholder="e.g. 8.8.8.8"
            aria-label="Enter IOC value — IP address, file hash, or domain"
            rows={1}
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck="false"
          />
          <div className="ioc-search-actions">
            <button
              type="button"
              className="ioc-clear-btn mono"
              onClick={clearLookup}
              disabled={loading || !hasLookupState}
              aria-label="Clear IOC lookup input and results"
            >
              CLEAR
            </button>
            <button
              type="button"
              className="ioc-lookup-btn ioc-btn-lookup"
              onClick={() => runLookup()}
              disabled={loading || !value.trim() || !detectedType}
              aria-label="Run IOC lookup"
            >
              {loading ? (
                <span className="btn-loading" aria-label="Searching...">
                  <span /><span /><span />
                </span>
              ) : 'LOOKUP'}
            </button>
          </div>
        </div>

        <div className="ioc-controls">
          {detectedType && (
            <span className="ioc-detected-badge mono" aria-live="polite">
              Detected: {TYPE_LABELS[detectedType] || detectedType.toUpperCase()}
            </span>
          )}
          {detectedType === 'ip' && (
            <Checkbox
              id="ioc-include-greynoise"
              checked={includeGreynoise}
              onCheckedChange={setIncludeGreynoise}
              label="GreyNoise — optional, per lookup (uses weekly quota)"
              className="ioc-greynoise-opt mono"
            />
          )}
        </div>

        {/* QA-P2-5: the old placeholder crammed all 3 example formats into
            one "/"-separated string, which read as a single copy-pasteable
            value. One example in the placeholder; the rest spelled out here.
            Placed after .ioc-controls (not between the textarea and
            controls) so it doesn't interpose in the border-merge
            (.ioc-controls' negative margin-top overlaps the textarea's
            bottom border to look like one connected input — Gemini review
            on the first version of this fix caught the layout break). */}
        <p className="ioc-input-hint mono">
          IP address, file hash (MD5/SHA1/SHA256), or domain/URL
        </p>

        <p className="ioc-privacy-notice mono" role="note">
          {'// Lookups are sent to third-party enrichment APIs (see Privacy Policy).'}<br />
          {'// Results cached on this server (6h IOC, 1h GreyNoise). Sign in to save IOCs to your watchlist.'}
        </p>

        <IOCQuotaPanel />
      </div>

      {/* ── Error state ── */}
      {error && (
        <div className="ioc-error-block" role="alert" aria-live="assertive">
          <span className="ioc-error-mark mono" aria-hidden="true">ERR</span>
          <span>
            {error}
            {errorRequestId && (
              <>
                {' '}
                (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                  ref: {errorRequestId}
                </a>)
              </>
            )}
          </span>
        </div>
      )}

      {/* ── Results ── */}
      {hasResult && (
        <div className="ioc-results" aria-label={`Results for ${result.value}`}>
          <div className="ioc-results-header">
            <span className="result-value mono" aria-label={`IOC: ${result.value}`}>
              {result.value}
            </span>
            <div className="result-header-badges">
              <span className="result-type-badge mono">
                {result.type?.toUpperCase()}
              </span>
              {result.cached && (
                <span className="result-cached-badge mono" title="Served from 6h cache">
                  CACHED
                </span>
              )}
            </div>
          </div>

          {result.type === 'ip' ? (
            <IPResultBody
              result={result}
              onOpenCve={investigation?.openCveById}
              onViewActorTechniques={
                investigation
                  ? (actor) => investigation.pivotToAtlasActor(actor, {
                      type: 'ioc',
                      id: result.value,
                      title: result.value,
                    })
                  : undefined
              }
            />
          ) : (
            <>
              <ThreatBar
                malicious={result.malicious_votes ?? 0}
                total={result.total_votes ?? 0}
              />
              <DetailGrid result={result} />
            </>
          )}

          {result.type === 'ip' ? null : result.greynoise_sentence && (
            <EnrichmentBlock
              heading="GREYNOISE"
              sentence={result.greynoise_sentence}
              tip={DOMAIN_TERM_TIPS.greynoise}
            >
              {result.greynoise?.link && (
                <a
                  className="ioc-enrichment-link mono"
                  href={result.greynoise.link}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View on GreyNoise &rarr;
                </a>
              )}
            </EnrichmentBlock>
          )}

          {result.type === 'hash' && result.malwarebazaar?.malware_family && (
            <p className="ioc-malware-family mono" role="status">
              Malware family: <strong>{result.malwarebazaar.malware_family}</strong>
            </p>
          )}

          {result.type === 'hash' && result.malwarebazaar_sentence && (
            <EnrichmentBlock
              heading="MALWAREBAZAAR"
              sentence={result.malwarebazaar_sentence}
              tip={DOMAIN_TERM_TIPS.malwarebazaar}
            />
          )}

          {result.type === 'domain' && result.urlhaus_sentence && (
            <EnrichmentBlock
              heading="URLHAUS"
              sentence={result.urlhaus_sentence}
              tip={DOMAIN_TERM_TIPS.urlhaus}
            >
              {result.urlhaus?.reference && (
                <a
                  className="ioc-enrichment-link mono"
                  href={result.urlhaus.reference}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  URLhaus record &rarr;
                </a>
              )}
            </EnrichmentBlock>
          )}

          {result.type !== 'ip' && (<OtxEnrichment result={result} onOpenCve={investigation?.openCveById} />)}

          <ActionRow
            result={result}
            onCopy={copyReport}
            copied={copied}
            onSaveWatchlist={authed ? handleSaveWatchlist : null}
            watchlistSaving={watchlistSaving}
            watchlistSaved={watchlistSaved}
          />
        </div>
      )}

      <WatchlistPanel
        items={watchlistItems}
        loading={watchlistLoading}
        error={watchlistError}
        errorRequestId={watchlistErrorRequestId}
        onRemove={handleRemoveWatchlist}
        removingId={watchlistRemovingId}
        onRerun={handleRerun}
        authed={authed}
      />

      {/* ── History ── */}
      {history.length > 0 && (
        <div className="ioc-history" aria-label="Recent lookups this session">
          <h2 className="ioc-history-heading mono">{formatSectionHeading('// RECENT')}</h2>
          <div className="history-list" role="list">
            {history.map(item => (
              <div key={item.value} role="listitem">
                <HistoryItem item={item} onRerun={handleRerun} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Idle state ── */}
      {!hasResult && !error && !loading && history.length === 0 && (
        <IdleLookupState />
      )}

    </section>
  )
}
