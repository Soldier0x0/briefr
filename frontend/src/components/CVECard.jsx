import { useState } from 'react'
import { copyToClipboard } from '../utils/report.js'
import { formatAbsolute } from '../utils/timezone.js'
import { publishedAgeClass } from '../utils/cveAge.js'
import { useMomentumScore } from '../utils/momentumCache.js'
import {
  daysUntilDue,
  kevAccentBarClass,
  kevDueUrgencyClass,
  kevDueLabel,
} from '../utils/kevDeadline.js'
import CveDescriptionClamp from './CveDescriptionClamp.jsx'
import './CVECard.css'

function timeAgo(isoString) {
  if (!isoString) return ''
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

function severityClass(sev) {
  const s = (sev || '').toLowerCase()
  if (s === 'critical') return 'critical'
  if (s === 'high')     return 'high'
  if (s === 'medium')   return 'medium'
  if (s === 'low')      return 'low'
  return 'unknown'
}

function cvssBadgeClass(score, severity) {
  const fromSev = severityClass(severity)
  if (fromSev !== 'unknown') return fromSev
  if (score == null) return 'unknown'
  if (score >= 9.0) return 'critical'
  if (score >= 7.0) return 'high'
  if (score >= 4.0) return 'medium'
  if (score > 0) return 'low'
  return 'unknown'
}

export default function CVECard({
  cve,
  onSelect,
  selected,
  onToggleSelect,
  timezone = 'UTC',
  navSelected,
  cardRef,
  isNew,
  inThread = false,
  onInvestigate,
  onLookupIoc,
  exposureScore = 0,
  watchlistState = null,
  onWatchlistPin,
}) {
  const [shareCopied, setShareCopied] = useState(false)
  const momentumScore = useMomentumScore(cve.cve_id)
  const epss =
    typeof cve.epss_score === 'number' && cve.epss_score >= 0
      ? cve.epss_score
      : null
  const products = Array.isArray(cve.affected_products) ? cve.affected_products : []
  const cwes = Array.isArray(cve.cwe_ids) ? cve.cwe_ids : []
  const kevDueDays = cve.is_kev ? daysUntilDue(cve.kev_due_date) : null
  const kevDueText = kevDueLabel(kevDueDays)
  const accentClass = cve.is_kev ? kevAccentBarClass(kevDueDays) : 'accent-neutral'
  const cvssClass = cvssBadgeClass(cve.cvss_score, cve.severity)

  function handleClick() {
    if (onSelect) onSelect(cve)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (onSelect) onSelect(cve)
    }
  }

  function handleCheckChange(e) {
    e.stopPropagation()
    if (onToggleSelect) onToggleSelect(cve)
  }

  function handleCheckClick(e) {
    e.stopPropagation()
  }

  function handleInvestigate(e) {
    e.stopPropagation()
    onInvestigate?.(cve)
  }

  function handleLookupIoc(e) {
    e.stopPropagation()
    onLookupIoc?.(cve)
  }

  async function handleShare(e) {
    e.stopPropagation()
    const desc = (cve.description || '').slice(0, 60).trimEnd()
    const url = `https://projectjupiter.in/cve/${cve.cve_id}`
    const text = `${cve.cve_id} — ${desc}\nvia BRIEFR: ${url}`
    const ok = await copyToClipboard(text)
    if (ok) {
      setShareCopied(true)
      setTimeout(() => setShareCopied(false), 1500)
    }
  }

  function handleWatchlistPin(e) {
    e.stopPropagation()
    onWatchlistPin?.()
  }

  const isPinned = watchlistState === 'pin'

  return (
    <article
      ref={cardRef}
      className={`cve-card ${accentClass}${selected ? ' cve-selected' : ''}${navSelected ? ' cve-nav-selected' : ''}${inThread ? ' cve-card-in-thread' : ''}${isPinned ? ' cve-card-pinned' : ''}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`CVE ${cve.cve_id}, severity ${cve.severity || 'unknown'}. Click to view details.`}
      aria-current={navSelected ? 'true' : undefined}
    >
      {/* Custom rectangular checkbox — top-left, hover-only */}
      <label
        className="card-checkbox-wrap"
        onClick={handleCheckClick}
        aria-label={`Select ${cve.cve_id} for bulk report`}
      >
        <input
          type="checkbox"
          className="card-checkbox-input"
          checked={!!selected}
          onChange={handleCheckChange}
          tabIndex={-1}
        />
        <span className="card-checkbox-box" aria-hidden="true" />
      </label>

      {inThread && (
        <span className="cve-thread-badge mono" aria-label="In investigation thread">
          IN THREAD
        </span>
      )}

      {isNew && (
        <span className="cve-new-badge mono" aria-label="New since your last visit">
          NEW
        </span>
      )}

      {/* Share button — top-right, hover-only */}
      <div className="card-share-wrap">
        <button
          className="card-share-btn"
          onClick={handleShare}
          aria-label={`Copy share link for ${cve.cve_id}`}
          tabIndex={-1}
        >
          &#x2197;
        </button>
        {shareCopied && (
          <span className="share-tooltip mono" role="status" aria-live="polite">
            Link copied
          </span>
        )}
      </div>

      {/* Top row: ID + badges */}
      <div className="cve-top">
        <span className="cve-id" aria-label={`CVE ID: ${cve.cve_id}`}>
          {cve.cve_id}
          {momentumScore > 0.5 && (
            <span
              className="cve-momentum-arrow"
              title="Rising threat momentum — recent PoC activity, mentions, or exploitation reports are accelerating for this CVE"
              aria-label="Rising threat momentum"
            >
              ↑
            </span>
          )}
        </span>
        <div className="cve-badges" aria-label="CVE attributes">
          {cve.is_kev && (
            <span className="badge badge-kev" title="Listed in CISA Known Exploited Vulnerabilities">
              KEV
            </span>
          )}
          {isPinned && (
            <span className="badge badge-pin" title="Pinned to watchlist">
              PIN
            </span>
          )}
          {kevDueText && (
            <span
              className={`badge badge-kev-due ${kevDueUrgencyClass(kevDueDays)}`}
              title={`Federal remediation deadline: ${cve.kev_due_date}`}
            >
              {kevDueText}
            </span>
          )}
          {cve.has_poc && (
            <span className="badge badge-poc" title="Public exploit or PoC reference in NVD">
              PoC
            </span>
          )}
          {cve.cvss_score != null && (
            <span
              className={`badge badge-cvss badge-cvss-${cvssClass}`}
              title={`CVSS score: ${cve.cvss_score} (${cve.severity || 'unknown'})`}
            >
              CVSS {cve.cvss_score.toFixed(1)}
            </span>
          )}
          {cve.patch_available && (
            <span className="badge badge-patch" title="Patch available">
              Patch
            </span>
          )}
          {exposureScore > 0 && (
            <span className="badge badge-exposure" title={`Exposure score ${exposureScore} — how closely this CVE matches your stack. Higher = more relevant to your environment.`}>
              {exposureScore}
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      {cve.description && (
        <CveDescriptionClamp text={cve.description} maxLines={2} />
      )}

      {/* Plain English summary */}
      {cve.summary && (
        <blockquote className="cve-summary" aria-label="Plain English summary">
          {cve.summary}
        </blockquote>
      )}

      {/* EPSS bar */}
      {epss != null && epss > 0 && (
        <div className="cve-epss" title={`EPSS ${(epss * 100).toFixed(1)}% — probability this vulnerability will be exploited in the wild within 30 days (FIRST.org model)`} aria-label={`EPSS exploitation probability: ${(epss * 100).toFixed(1)}%`}>
          <div className="epss-track" role="progressbar" aria-valuenow={Math.round(epss * 100)} aria-valuemin={0} aria-valuemax={100}>
            <div
              className="epss-fill"
              style={{ width: `${Math.min(epss * 100, 100)}%` }}
            />
          </div>
          <span className="epss-label">EPSS {(epss * 100).toFixed(1)}%</span>
        </div>
      )}

      {/* Meta row */}
      <div className="cve-meta">
        {products.length > 0 && (
          <span className="meta-item" aria-label={`Affected: ${products.slice(0, 3).join(', ')}`}>
            <span className="meta-key">affects</span>
            <span className="meta-val">
              {products.slice(0, 3).map(p => p.split(':')[1] || p).join(', ')}
              {products.length > 3 && ` +${products.length - 3}`}
            </span>
          </span>
        )}
        {cwes.length > 0 && (
          <span className="meta-item" aria-label={`Weakness: ${cwes[0]}`}>
            <span className="meta-key">weakness</span>
            <span className="meta-val">{cwes[0]}</span>
          </span>
        )}
        {cve.mitre_technique && (
          <span className="meta-item" aria-label={`MITRE technique: ${cve.mitre_technique}`}>
            <span className="meta-key">technique</span>
            <span className="meta-val">{cve.mitre_technique}</span>
          </span>
        )}
        <span className="meta-item meta-time" aria-label={`Published: ${cve.published}`}>
          <span className="meta-key">published</span>
          <span
            className={`meta-val time-tooltip-wrap ${publishedAgeClass(cve.published)}`}
            title={formatAbsolute(cve.published, timezone)}
          >
            {timeAgo(cve.published)}
          </span>
        </span>
      </div>

      {(onInvestigate || onLookupIoc || onWatchlistPin) && (
        <div className="cve-card-actions" role="group" aria-label="Investigation actions">
          {onWatchlistPin && (
            <button
              type="button"
              className={`cve-action-btn mono${isPinned ? ' cve-action-btn-active' : ''}`}
              onClick={handleWatchlistPin}
              aria-pressed={isPinned}
              aria-label={isPinned ? `Unpin ${cve.cve_id}` : `Pin ${cve.cve_id} to watchlist`}
            >
              {isPinned ? 'Unpin' : 'Pin'}
            </button>
          )}
          {onInvestigate && (
            <button
              type="button"
              className="cve-action-btn mono"
              onClick={handleInvestigate}
              disabled={inThread}
              aria-label={`Add ${cve.cve_id} to investigation`}
            >
              {inThread ? 'In thread' : 'Investigate'}
            </button>
          )}
          {onLookupIoc && (
            <button
              type="button"
              className="cve-action-btn cve-action-btn-secondary mono"
              onClick={handleLookupIoc}
              aria-label={`Look up indicators from ${cve.cve_id} in IOC tab`}
            >
              Lookup in IOC
            </button>
          )}
        </div>
      )}
    </article>
  )
}
                                                                                                   