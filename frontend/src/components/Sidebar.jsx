import { useState, useEffect } from 'react'
import { fetchKEVDeadlines, fetchStatsTimeline, fetchTopTechniques } from '../api.js'
import { getSavedStack } from '../utils/cveFilters.js'
import { daysUntilDue, kevAccentBarClass, kevDueUrgencyClass, kevDueLabel } from '../utils/kevDeadline.js'
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

const SPARKLINE_DAYS = 14

const KEV_PREVIEW = 5

const TOP_TECHNIQUES_LIMIT = 5

// Module-level session cache (5 min) so returning to the BRIEF tab does not
// refetch and flash-load the sidebar every time (same pattern as the
// Incidents feed cache).
const SIDEBAR_CACHE_MS = 5 * 60 * 1000
const sidebarCache = new Map()

function getCached(key) {
  const hit = sidebarCache.get(key)
  if (hit && Date.now() - hit.at < SIDEBAR_CACHE_MS) return hit.value
  return undefined
}

function setCached(key, value) {
  sidebarCache.set(key, { value, at: Date.now() })
}

function SidebarSkeleton({ rows = 3, tall = false }) {
  return (
    <div className="sidebar-skeleton" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={`sidebar-skeleton-row${tall ? ' sidebar-skeleton-tall' : ''}`} />
      ))}
    </div>
  )
}

export default function Sidebar({ filters, onFiltersChange, stats }) {
  const [kevDeadlines, setKevDeadlines] = useState([])
  const [kevExpanded, setKevExpanded] = useState(false)
  const [kevLoading, setKevLoading] = useState(true)
  const [kevError, setKevError] = useState(false)
  const [topTechniques, setTopTechniques] = useState([])
  const [techniquesLoading, setTechniquesLoading] = useState(true)
  const [sparkBars, setSparkBars] = useState([])
  const [sparkLoading, setSparkLoading] = useState(true)
  const savedStack = getSavedStack()
  const visibleKev = kevExpanded ? kevDeadlines : kevDeadlines.slice(0, KEV_PREVIEW)
  const hiddenKevCount = Math.max(0, kevDeadlines.length - KEV_PREVIEW)
  const sparkMax = Math.max(...sparkBars, 1)

  useEffect(() => {
    const hit = getCached('spark')
    if (hit !== undefined) {
      setSparkBars(hit)
      setSparkLoading(false)
      return
    }
    let cancelled = false
    setSparkLoading(true)
    fetchStatsTimeline(SPARKLINE_DAYS)
      .then(data => {
        if (cancelled) return
        const bars = Array.isArray(data) ? data.map(d => d.count || 0) : []
        setCached('spark', bars)
        setSparkBars(bars)
      })
      .catch(() => {
        if (!cancelled) setSparkBars([])
      })
      .finally(() => {
        if (!cancelled) setSparkLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const hit = getCached('kev')
    if (hit !== undefined) {
      setKevDeadlines(hit)
      setKevLoading(false)
      return
    }
    let cancelled = false
    // sort=urgent returns entries sorted by due_date ASC (soonest first)
    setKevLoading(true)
    setKevError(false)
    fetchKEVDeadlines('urgent')
      .then(data => {
        if (cancelled) return
        const rows = (data.data || []).slice(0, 10)
        setCached('kev', rows)
        setKevDeadlines(rows)
      })
      .catch(() => {
        if (!cancelled) setKevError(true)
      })
      .finally(() => {
        if (!cancelled) setKevLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const hit = getCached('tech')
    if (hit !== undefined) {
      setTopTechniques(hit)
      setTechniquesLoading(false)
      return
    }
    let cancelled = false
    setTechniquesLoading(true)
    fetchTopTechniques(TOP_TECHNIQUES_LIMIT)
      .then(data => {
        if (cancelled) return
        const rows = data.data || []
        setCached('tech', rows)
        setTopTechniques(rows)
      })
      .catch(() => {
        if (!cancelled) setTopTechniques([])
      })
      .finally(() => {
        if (!cancelled) setTechniquesLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  function handleTechniqueClick(techniqueId) {
    const next = filters.technique === techniqueId ? '' : techniqueId
    onFiltersChange({ technique: next })
  }

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
        <Toggle
          id="toggle-my-stack"
          label="My stack only"
          checked={!!filters.my_stack_only}
          onChange={val => {
            if (val && !savedStack) return
            if (val) {
              onFiltersChange({ my_stack_only: true, stack: savedStack })
            } else {
              const next = { my_stack_only: false }
              if (filters.stack === savedStack) next.stack = ''
              onFiltersChange(next)
            }
          }}
        />
        {!savedStack && (
          <p className="sidebar-filter-hint">
            Enter your stack in the Feed tab filter bar, then enable this filter.
          </p>
        )}
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
        {filters.technique && (
          <div className="active-stack" aria-label={`Active ATT&CK filter: ${filters.technique}`}>
            <span className="stack-key">TECH</span>
            <span className="stack-val">{filters.technique}</span>
            <button
              className="stack-clear"
              onClick={() => onFiltersChange({ technique: '' })}
              aria-label="Clear technique filter"
            >
              x
            </button>
          </div>
        )}
      </section>

      {/* ── Section 2: Sparkline ── */}
      <section className="sidebar-section" aria-labelledby="sparkline-heading">
        <h2 id="sparkline-heading" className="sidebar-heading">14-DAY ACTIVITY</h2>
        {sparkLoading ? (
          <SidebarSkeleton rows={1} tall />
        ) : sparkBars.length === 0 ? (
          <p className="sidebar-empty">No publication data yet.</p>
        ) : (
          <>
            <div className="sparkline" aria-label="14-day CVE publication counts">
              {sparkBars.map((val, i) => (
                <div
                  key={i}
                  className={`spark-bar${i === sparkBars.length - 1 ? ' spark-today' : ''}`}
                  style={{ height: `${Math.round((val / sparkMax) * 100)}%` }}
                  title={i === sparkBars.length - 1 ? `Today: ${val}` : `Day ${i + 1}: ${val}`}
                  aria-label={i === sparkBars.length - 1 ? `Today: ${val} CVEs` : `${val} CVEs`}
                />
              ))}
            </div>
            <div className="sparkline-labels" aria-hidden="true">
              <span>14d ago</span>
              <span>today</span>
            </div>
          </>
        )}
      </section>

      {/* ── Section 3: KEV Deadlines ── */}
      <section className="sidebar-section" aria-labelledby="kev-heading">
        <h2 id="kev-heading" className="sidebar-heading">KEV DEADLINES (BY DUE DATE)</h2>
        {kevLoading && <SidebarSkeleton rows={3} />}
        {!kevLoading && kevError && (
          <p className="sidebar-empty">Unable to load deadlines.</p>
        )}
        {!kevLoading && !kevError && kevDeadlines.length === 0 && (
          <p className="sidebar-empty">No KEV deadlines in database.</p>
        )}
        <ul className="kev-list" aria-label="Upcoming KEV remediation deadlines">
          {visibleKev.map(entry => {
            const days = daysUntilDue(entry.due_date)
            const badgeClass = kevDueUrgencyClass(days)
            const badgeLabel = kevDueLabel(days) || 'unknown'
            const accentClass = kevAccentBarClass(days)
            return (
              <li key={entry.cve_id} className={`kev-item ${accentClass}`}>
                <div className="kev-item-top">
                  <span className="kev-cve-id" aria-label={`CVE ID: ${entry.cve_id}`}>
                    {entry.cve_id}
                  </span>
                  {entry.ransomware_use && (
                    <span
                      className="kev-badge badge-ransomware"
                      title="Known ransomware campaign use (CISA KEV)"
                      aria-label="Known ransomware campaign use"
                    >
                      RANSOMWARE
                    </span>
                  )}
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

      {/* ── Section 4: Top Techniques ── */}
      <section className="sidebar-section" aria-labelledby="techniques-heading">
        <h2 id="techniques-heading" className="sidebar-heading">// TOP TECHNIQUES THIS WEEK</h2>
        {techniquesLoading && <SidebarSkeleton rows={3} />}
        {!techniquesLoading && topTechniques.length === 0 && (
          <p className="sidebar-empty">No technique data yet.</p>
        )}
        <ul className="technique-list" aria-label="Most frequent ATT&CK techniques in database">
          {topTechniques.map(tech => {
            const active = filters.technique === tech.technique_id
            return (
              <li key={tech.technique_id}>
                <button
                  type="button"
                  className={`technique-row${active ? ' technique-row-active' : ''}`}
                  onClick={() => handleTechniqueClick(tech.technique_id)}
                  aria-pressed={active}
                  aria-label={`Filter CVEs by ${tech.technique_id}: ${tech.name}, ${tech.cve_count ?? tech.count} CVEs`}
                >
                  <span className="technique-row-id mono">{tech.technique_id}</span>
                  <span className="technique-row-name">{tech.name}</span>
                  <span className="technique-row-count mono">{tech.cve_count ?? tech.count}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </section>


    </aside>
  )
}
