import { useState, useEffect, useRef } from 'react'
import { fetchBrief } from '../api.js'
import CVECard from './CVECard.jsx'
import { daysUntilDue, kevDueLabel } from '../utils/kevDeadline.js'
import './MorningBrief.css'

const REASON_LABELS = {
  epss_mover: 'EPSS mover',
  new_kev: 'New KEV',
  kev_due_soon: 'KEV due soon',
  stack_match: 'Stack match',
}

function reasonChips(reasons = []) {
  return reasons.map(r => REASON_LABELS[r] || r)
}

function BriefSection({ id, title, count, items, onSelectCVE, timezone, emptyHint }) {
  const [collapsed, setCollapsed] = useState(false)
  if (!count && !items?.length) {
    return (
      <section className="morning-brief-section" aria-labelledby={`brief-section-${id}`}>
        <header className="morning-brief-section-head">
          <h3 id={`brief-section-${id}`} className="morning-brief-section-title mono">
            {title}
          </h3>
          <span className="morning-brief-section-count mono">0</span>
        </header>
        {emptyHint && <p className="morning-brief-empty mono">{emptyHint}</p>}
      </section>
    )
  }

  return (
    <section className="morning-brief-section" aria-labelledby={`brief-section-${id}`}>
      <header className="morning-brief-section-head">
        <button
          type="button"
          className="morning-brief-section-toggle"
          onClick={() => setCollapsed(v => !v)}
          aria-expanded={!collapsed}
          aria-controls={`brief-section-body-${id}`}
        >
          <h3 id={`brief-section-${id}`} className="morning-brief-section-title mono">
            {title}
          </h3>
          <span className="morning-brief-section-count mono">{count}</span>
        </button>
      </header>
      {!collapsed && (
        <div id={`brief-section-body-${id}`} className="morning-brief-section-body">
          {items.map(item => (
            <div key={item.cve_id} className="morning-brief-card-wrap">
              <div className="morning-brief-reasons" aria-label="Brief reasons">
                {reasonChips(item.reasons).map(label => (
                  <span key={label} className="morning-brief-reason-chip mono">{label}</span>
                ))}
                {item.epss_delta != null && (
                  <span className="morning-brief-reason-chip mono morning-brief-reason-epss">
                    EPSS +{(item.epss_delta * 100).toFixed(1)}%
                  </span>
                )}
                {item.kev_due_date && (
                  <span className="morning-brief-reason-chip mono morning-brief-reason-due">
                    {kevDueLabel(daysUntilDue(item.kev_due_date))}
                  </span>
                )}
              </div>
              <CVECard
                cve={{
                  ...item,
                  description: item.summary || item.cve_id,
                }}
                onSelect={() => onSelectCVE(item)}
                timezone={timezone}
              />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export default function MorningBrief({
  stack = '',
  sinceHours = 24,
  onSelectCVE,
  onOpenFullFeed,
  timezone = 'UTC',
}) {
  const [brief, setBrief] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const seqRef = useRef(0)

  useEffect(() => {
    const seq = ++seqRef.current
    let cancelled = false
    setLoading(true)
    setError(false)

    fetchBrief({ stack, sinceHours, limit: 10 })
      .then(data => {
        if (cancelled || seq !== seqRef.current) return
        setBrief(data)
      })
      .catch(() => {
        if (cancelled || seq !== seqRef.current) return
        setBrief(null)
        setError(true)
      })
      .finally(() => {
        if (cancelled || seq !== seqRef.current) return
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [stack, sinceHours])

  const queue = brief?.action_queue || []
  const sections = brief?.sections || {}

  return (
    <section className="morning-brief" aria-label="Morning brief action queue">
      <div className="morning-brief-header">
        <div>
          <h2 className="morning-brief-heading mono">// MORNING BRIEF</h2>
          <p className="morning-brief-sub">
            Ranked action queue since your last visit window
            {brief?.meta?.since_hours ? ` (${brief.meta.since_hours}h)` : ''}.
          </p>
        </div>
        {onOpenFullFeed && (
          <button
            type="button"
            className="morning-brief-feed-link mono"
            onClick={onOpenFullFeed}
          >
            Open full feed →
          </button>
        )}
      </div>

      {loading && (
        <div className="morning-brief-loading" aria-live="polite">
          <div className="morning-brief-skeleton" aria-hidden="true" />
          <div className="morning-brief-skeleton" aria-hidden="true" />
        </div>
      )}

      {error && !loading && (
        <p className="morning-brief-error mono" role="alert">
          Could not load morning brief — check backend connectivity.
        </p>
      )}

      {!loading && !error && brief && (
        <>
          {queue.length > 0 && (
            <div className="morning-brief-queue">
              <h3 className="morning-brief-queue-title mono">Priority queue</h3>
              <ul className="morning-brief-queue-list">
                {queue.map(item => (
                  <li key={item.cve_id}>
                    <button
                      type="button"
                      className="morning-brief-queue-row"
                      onClick={() => onSelectCVE(item)}
                    >
                      <span className="morning-brief-queue-id mono">{item.cve_id}</span>
                      <span className="morning-brief-queue-reasons">
                        {reasonChips(item.reasons).join(' · ')}
                      </span>
                      {item.severity && (
                        <span className={`morning-brief-queue-sev sev-${(item.severity || '').toLowerCase()}`}>
                          {item.severity}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="morning-brief-sections">
            <BriefSection
              id="kev-due"
              title={sections.kev_due_soon?.title || 'KEV due soon'}
              count={sections.kev_due_soon?.count || 0}
              items={sections.kev_due_soon?.items || []}
              onSelectCVE={onSelectCVE}
              timezone={timezone}
              emptyHint="No KEV remediation deadlines in the next window."
            />
            <BriefSection
              id="new-kev"
              title={sections.new_kev?.title || 'New KEV entries'}
              count={sections.new_kev?.count || 0}
              items={sections.new_kev?.items || []}
              onSelectCVE={onSelectCVE}
              timezone={timezone}
              emptyHint="No new CISA KEV catalogue entries in this window."
            />
            <BriefSection
              id="epss"
              title={sections.epss_movers?.title || 'EPSS movers'}
              count={sections.epss_movers?.count || 0}
              items={sections.epss_movers?.items || []}
              onSelectCVE={onSelectCVE}
              timezone={timezone}
              emptyHint="No material EPSS increases tracked in this window."
            />
            {stack?.trim() && (
              <BriefSection
                id="stack"
                title={sections.stack_matches?.title || 'Stack activity'}
                count={sections.stack_matches?.count || 0}
                items={sections.stack_matches?.items || []}
                onSelectCVE={onSelectCVE}
                timezone={timezone}
                emptyHint="No recent CVE activity matching your stack terms."
              />
            )}
          </div>
        </>
      )}
    </section>
  )
}
