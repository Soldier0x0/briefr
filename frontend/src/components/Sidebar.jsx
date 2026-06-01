import { useState, useEffect } from 'react'
import { fetchKEVDeadlines } from '../api.js'
import './Sidebar.css'

function Toggle({ label, checked, onChange, id }) {
  return (
    <div className="toggle-row">
      <button
        id={id}
        role="switch"
        aria-checked={checked}
        aria-label={label}
        className={`toggle${checked ? ' toggle-on' : ''}`}
        onClick={() => onChange(!checked)}
      >
        <span className="toggle-thumb" aria-hidden="true" />
      </button>
      <label htmlFor={id} className="toggle-label" onClick={() => onChange(!checked)}>
        {label}
      </label>
    </div>
  )
}

function daysUntil(dateStr) {
  if (!dateStr) return null
  const diff = new Date(dateStr).getTime() - Date.now()
  return Math.ceil(diff / 86400000)
}

function deadlineBadgeClass(days) {
  if (days === null) return 'badge-neutral'
  if (days < 0)  return 'badge-overdue'
  if (days < 5)  return 'badge-urgent'
  if (days < 14) return 'badge-soon'
  return 'badge-ok'
}

function deadlineBadgeLabel(days) {
  if (days === null) return 'unknown'
  if (days < 0)  return 'OVERDUE'
  if (days === 0) return 'today'
  return `${days}d left`
}

// Build a rough 14-day activity distribution from total + last_24h stats
function buildSparkline(stats) {
  const bars = Array(15).fill(0)
  if (!stats) return bars
  const total = (stats.critical || 0) + (stats.high || 0)
  const daily = Math.max(1, Math.floor(total / 14))
  const seed = stats.critical || 7
  for (let i = 0; i < 15; i++) {
    const noise = ((seed * (i + 3)) % 7) - 3
    bars[i] = Math.max(1, daily + noise)
  }
  bars[14] = Math.max(1, stats.last_24h || daily)
  return bars
}

const DATA_SOURCES = [
  { name: 'NVD (NIST)', url: 'https://nvd.nist.gov/' },
  { name: 'CISA KEV', url: 'https://www.cisa.gov/known-exploited-vulnerabilities-catalog' },
  { name: 'FIRST EPSS', url: 'https://www.first.org/epss/' },
  { name: 'OSV.dev', url: 'https://osv.dev/' },
  { name: 'VirusTotal', url: 'https://www.virustotal.com/' },
]

const KEV_PREVIEW = 5

export default function Sidebar({ filters, onFiltersChange, stats }) {
  const [kevDeadlines, setKevDeadlines] = useState([])
  const [kevExpanded, setKevExpanded] = useState(false)
  const sparkBars = buildSparkline(stats)
  const visibleKev = kevExpanded ? kevDeadlines : kevDeadlines.slice(0, KEV_PREVIEW)
  const hiddenKevCount = Math.max(0, kevDeadlines.length - KEV_PREVIEW)
  const sparkMax = Math.max(...sparkBars, 1)

  useEffect(() => {
    // sort=recent returns entries sorted by dateAdded DESC (most recently added first)
    fetchKEVDeadlines('recent')
      .then(data => setKevDeadlines((data.data || []).slice(0, 10)))
      .catch(() => {})
  }, [])

  return (
    <aside className="sidebar" aria-label="Filters and supplementary data">

      {/* ── Section 1: Filters ── */}
      <section className="sidebar-section" aria-labelledby="filter-heading">
        <h2 id="filter-heading" className="sidebar-heading">YOUR FILTERS</h2>

        <Toggle
          id="toggle-kev"
          label="KEV only"
          checked={filters.kev_only}
          onChange={val => onFiltersChange({ kev_only: val })}
        />
        <Toggle
          id="toggle-poc"
          label="PoC public"
          checked={filters.poc_only}
          onChange={val => onFiltersChange({ poc_only: val })}
        />
        <Toggle
          id="toggle-epss"
          label="EPSS > 50%"
          checked={filters.epss_min === 0.5}
          onChange={val => onFiltersChange({ epss_min: val ? 0.5 : null })}
        />
        {filters.stack && (
          <div className="active-stack" aria-label={`Active stack filter: ${filters.stack}`}>
            <span className="stack-key">STACK</span>
            <span className="stack-val">{filters.stack}</span>
            <button
              className="stack-clear"
              onClick={() => onFiltersChange({ stack: '' })}
              aria-label="Clear stack filter"
            >
              x
            </button>
          </div>
        )}
      </section>

      {/* ── Section 2: Sparkline ── */}
      <section className="sidebar-section" aria-labelledby="sparkline-heading">
        <h2 id="sparkline-heading" className="sidebar-heading">14-DAY ACTIVITY</h2>
        <div className="sparkline" aria-label="14-day CVE activity chart">
          {sparkBars.map((val, i) => (
            <div
              key={i}
              className={`spark-bar${i === 14 ? ' spark-today' : ''}`}
              style={{ height: `${Math.round((val / sparkMax) * 100)}%` }}
              title={i === 14 ? `Today: ${val}` : `Day ${i + 1}: ~${val}`}
              aria-label={i === 14 ? `Today: ${val} CVEs` : `${val} CVEs`}
            />
          ))}
        </div>
        <div className="sparkline-labels" aria-hidden="true">
          <span>14d ago</span>
          <span>today</span>
        </div>
      </section>

      {/* ── Section 3: KEV Deadlines ── */}
      <section className="sidebar-section" aria-labelledby="kev-heading">
        <h2 id="kev-heading" className="sidebar-heading">KEV DEADLINES</h2>
        {kevDeadlines.length === 0 && (
          <p className="sidebar-empty">Loading deadlines...</p>
        )}
        <ul className="kev-list" aria-label="Upcoming KEV remediation deadlines">
          {visibleKev.map(entry => {
            const days = daysUntil(entry.due_date)
            const badgeClass = deadlineBadgeClass(days)
            const badgeLabel = deadlineBadgeLabel(days)
            return (
              <li key={entry.cve_id} className="kev-item">
                <div className="kev-item-top">
                  <span className="kev-cve-id" aria-label={`CVE ID: ${entry.cve_id}`}>
                    {entry.cve_id}
                  </span>
                  <span className={`kev-badge ${badgeClass}`} aria-label={`Status: ${badgeLabel}`}>
                    {badgeLabel}
                  </span>
                </div>
                {entry.short_description && (
                  <p className="kev-desc">{entry.short_description.slice(0, 80)}</p>
                )}
                {entry.date_added && (
                  <p className="kev-date-added mono" aria-label={`Date added to KEV: ${entry.date_added}`}>
                    {entry.date_added}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
        {hiddenKevCount > 0 && !kevExpanded && (
          <button
            type="button"
            className="kev-expand-btn mono"
            onClick={() => setKevExpanded(true)}
            aria-label={`Show ${hiddenKevCount} more KEV deadlines`}
          >
            + {hiddenKevCount} more
          </button>
        )}
        {kevExpanded && kevDeadlines.length > KEV_PREVIEW && (
          <button
            type="button"
            className="kev-expand-btn mono"
            onClick={() => setKevExpanded(false)}
            aria-label="Show fewer KEV deadlines"
          >
            Show less
          </button>
        )}
      </section>

      {/* ── Section 4: Data Sources ── */}
      <section className="sidebar-section" aria-labelledby="sources-heading">
        <h2 id="sources-heading" className="sidebar-heading">DATA SOURCES</h2>
        <ul className="sources-list" aria-label="Data sources used by BRIEFR">
          {DATA_SOURCES.map(src => (
            <li key={src.name} className="source-item">
              <span className="source-bullet" aria-hidden="true">--</span>
              <span>{src.name}</span>
            </li>
          ))}
        </ul>
      </section>

    </aside>
  )
}
