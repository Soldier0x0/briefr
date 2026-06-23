import { useState, useEffect, useRef } from 'react'
import { fetchChanges } from '../api.js'
import { scrollBehavior } from '../utils/motion.js'
import './WhatChangedPanel.css'

const FIELD_CHIPS = [
  { id: null, label: 'ALL' },
  { id: 'cvss_score', label: 'CVSS' },
  { id: 'epss_score', label: 'EPSS' },
  { id: 'is_kev', label: 'KEV' },
  { id: 'has_poc', label: 'PoC' },
]

const WINDOW_CHIPS = [
  { hours: 24, label: '24h' },
  { hours: 48, label: '48h' },
  { hours: 168, label: '7d' },
]

const FIELD_LABELS = {
  cvss_score: 'CVSS',
  epss_score: 'EPSS',
  is_kev: 'KEV',
  has_poc: 'PoC',
}

function timeAgo(isoString) {
  if (!isoString) return ''
  const raw = isoString.includes('T') ? isoString : isoString.replace(' ', 'T') + 'Z'
  const diff = Math.max(0, Date.now() - new Date(raw).getTime())
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatValue(field, value) {
  if (value === '' || value == null) return '—'
  if (field === 'is_kev' || field === 'has_poc') {
    const truthy = value === '1' || value === 'true' || value === true
    return truthy ? 'yes' : 'no'
  }
  if (field === 'epss_score') {
    const n = Number(value)
    if (!Number.isFinite(n)) return value
    return `${(n * 100).toFixed(1)}%`
  }
  if (field === 'cvss_score') {
    const n = Number(value)
    if (!Number.isFinite(n)) return value
    return n.toFixed(1)
  }
  return String(value)
}

function isVisibleChange(row) {
  return (
    formatValue(row.field_name, row.old_value)
    !== formatValue(row.field_name, row.new_value)
  )
}

export default function WhatChangedPanel({ onSelectCVE }) {
  const [fieldFilter, setFieldFilter] = useState(null)
  const [sinceHours, setSinceHours] = useState(24)
  const [changes, setChanges] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [collapsed, setCollapsed] = useState(false)
  const panelRef = useRef(null)
  const filtersInitialMountRef = useRef(true)

  function scrollPanelToTop() {
    const el = panelRef.current
    if (!el) return
    const top = el.getBoundingClientRect().top
    if (top >= 0) return
    window.scrollTo({
      top: window.scrollY + top - 8,
      behavior: scrollBehavior(),
    })
  }

  useEffect(() => {
    if (filtersInitialMountRef.current) {
      filtersInitialMountRef.current = false
    } else {
      scrollPanelToTop()
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    fetchChanges({ field: fieldFilter, sinceHours, limit: 50 })
      .then(data => {
        if (cancelled) return
        const rows = Array.isArray(data?.data) ? data.data : []
        setChanges(rows.filter(isVisibleChange))
      })
      .catch(err => {
        if (!cancelled) {
          setChanges([])
          setError(err?.message || 'Unable to load recent changes.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [fieldFilter, sinceHours])

  function handleRowClick(cveId) {
    if (!cveId || !onSelectCVE) return
    onSelectCVE({ cve_id: cveId })
  }

  return (
    <section
      ref={panelRef}
      className={`what-changed${collapsed ? ' what-changed--collapsed' : ''}`}
      aria-labelledby="what-changed-heading"
    >
      <div className="what-changed-header">
        <button
          type="button"
          className="what-changed-toggle"
          onClick={() => setCollapsed(c => !c)}
          aria-expanded={!collapsed}
          aria-controls="what-changed-body"
          aria-label={collapsed ? 'Expand what changed panel' : 'Collapse what changed panel'}
        >
          <span className={`what-changed-chevron${collapsed ? ' collapsed' : ''}`} aria-hidden="true">
            ▾
          </span>
        </button>
        <h2 id="what-changed-heading" className="what-changed-title mono">
          WHAT CHANGED
        </h2>
      </div>

      {!collapsed && (
        <div id="what-changed-body" className="what-changed-body">
          <div className="what-changed-filters" role="group" aria-label="Change field filters">
            {FIELD_CHIPS.map(chip => (
              <button
                key={chip.label}
                type="button"
                className={`what-changed-chip${fieldFilter === chip.id ? ' active' : ''}`}
                aria-pressed={fieldFilter === chip.id}
                onClick={() => setFieldFilter(chip.id)}
              >
                {chip.label}
              </button>
            ))}
          </div>
          <div className="what-changed-filters" role="group" aria-label="Change time window">
            {WINDOW_CHIPS.map(chip => (
              <button
                key={chip.hours}
                type="button"
                className={`what-changed-chip what-changed-chip-window${sinceHours === chip.hours ? ' active' : ''}`}
                aria-pressed={sinceHours === chip.hours}
                onClick={() => setSinceHours(chip.hours)}
              >
                {chip.label}
              </button>
            ))}
          </div>

          {loading && (
            <p className="what-changed-loading mono" aria-live="polite">
              Loading changes…
            </p>
          )}
          {!loading && error && (
            <p className="what-changed-empty">{error}</p>
          )}
          {!loading && !error && changes.length === 0 && (
            <p className="what-changed-empty">No tracked field changes in this window.</p>
          )}
          {!loading && !error && changes.length > 0 && (
            <ul className="what-changed-list" aria-label="Recent CVE field changes">
              {changes.map(row => {
                const fieldLabel = FIELD_LABELS[row.field_name] || row.field_name
                const oldVal = formatValue(row.field_name, row.old_value)
                const newVal = formatValue(row.field_name, row.new_value)
                return (
                  <li key={row.id}>
                    <button
                      type="button"
                      className="what-changed-row"
                      onClick={() => handleRowClick(row.cve_id)}
                      aria-label={`${row.cve_id}: ${fieldLabel} changed from ${oldVal} to ${newVal}. Open CVE details.`}
                    >
                      <span className="what-changed-cve mono">{row.cve_id}</span>
                      <span className="what-changed-field mono">{fieldLabel}</span>
                      <span className="what-changed-delta">
                        <span className="what-changed-old">{oldVal}</span>
                        <span className="what-changed-arrow" aria-hidden="true">→</span>
                        <span className="what-changed-new">{newVal}</span>
                      </span>
                      <span className="what-changed-time mono">{timeAgo(row.detected_at)}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
