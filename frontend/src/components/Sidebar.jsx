import { useState, useEffect } from 'react'
import { fetchStatsTimeline, fetchTopTechniques } from '../api.js'
import { getSavedStack } from '../utils/cveFilters.js'
import './Sidebar.css'

const SIDEBAR_FILTERS = [
  {
    id: 'toggle-kev',
    field: 'kev_only',
    label: 'KEV only',
    hint: 'Only CVEs on CISA\'s Known Exploited Vulnerabilities catalog.',
    toValue: (checked) => ({ kev_only: checked }),
    isChecked: (filters) => !!filters.kev_only,
  },
  {
    id: 'toggle-poc',
    field: 'poc_only',
    label: 'PoC public',
    hint: 'Only CVEs with a public proof-of-concept exploit available.',
    toValue: (checked) => ({ poc_only: checked }),
    isChecked: (filters) => !!filters.poc_only,
  },
  {
    id: 'toggle-epss',
    field: 'epss_min',
    label: 'EPSS > 50%',
    hint: 'Only CVEs with at least 50% EPSS probability of exploitation in 30 days.',
    toValue: (checked) => ({ epss_min: checked ? 0.5 : null }),
    isChecked: (filters) => filters.epss_min === 0.5,
  },
  {
    id: 'toggle-my-stack',
    field: 'my_stack_only',
    label: 'My stack only',
    hint: 'Limit results to CVEs matching your saved stack terms from the feed bar.',
    toValue: null,
    isChecked: (filters) => !!filters.my_stack_only,
  },
]

function Toggle({ label, hint, checked, onChange, id }) {
  return (
    <div className="toggle-cell">
      <div className="toggle-row">
        <button
          id={id}
          role="switch"
          aria-checked={checked}
          aria-label={label}
          aria-describedby={`${id}-hint`}
          className={`toggle${checked ? ' toggle-on' : ''}`}
          onClick={() => onChange(!checked)}
        >
          <span className="toggle-thumb" aria-hidden="true" />
        </button>
        <label htmlFor={id} className="toggle-label" onClick={() => onChange(!checked)}>
          {label}
        </label>
      </div>
      <p id={`${id}-hint`} className="toggle-hover-info" role="note">
        {hint}
      </p>
    </div>
  )
}

const SPARKLINE_DAYS = 14

const TOP_TECHNIQUES_LIMIT = 5

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
  const [topTechniques, setTopTechniques] = useState([])
  const [techniquesLoading, setTechniquesLoading] = useState(true)
  const [sparkBars, setSparkBars] = useState([])
  const [sparkLoading, setSparkLoading] = useState(true)
  const savedStack = getSavedStack()
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

  function handleFilterChange(def, checked) {
    if (def.field === 'my_stack_only') {
      if (checked && !savedStack) return
      if (checked) {
        onFiltersChange({ my_stack_only: true, stack: savedStack })
      } else {
        const next = { my_stack_only: false }
        if (filters.stack === savedStack) next.stack = ''
        onFiltersChange(next)
      }
      return
    }
    onFiltersChange(def.toValue(checked))
  }

  return (
    <aside className="sidebar" aria-label="Filters and supplementary data">

      {/* ── Section 1: Top Techniques ── */}
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

      {/* ── Section 2: Sparkline ── */}
      <section className="sidebar-section" aria-labelledby="sparkline-heading">
        <h2 id="sparkline-heading" className="sidebar-heading">14-DAY PUBLICATIONS</h2>
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

      {/* ── Section 3: Filters ── */}
      <section className="sidebar-section" aria-labelledby="filter-heading">
        <h2 id="filter-heading" className="sidebar-heading">YOUR FILTERS</h2>

        <div className="sidebar-filter-grid">
          {SIDEBAR_FILTERS.map(def => (
            <Toggle
              key={def.id}
              id={def.id}
              label={def.label}
              hint={def.hint}
              checked={def.isChecked(filters)}
              onChange={(val) => handleFilterChange(def, val)}
            />
          ))}
        </div>

        {!savedStack && (
          <p className="sidebar-filter-hint">
            Enter your stack in the Feed tab filter bar, then enable My stack only.
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

    </aside>
  )
}
