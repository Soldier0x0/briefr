import { useState, useEffect, useCallback } from 'react'
import { fetchStatsTimeline, fetchTopTechniques } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import { ingestLogUrl } from '../utils/adminLinks.js'
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
        <label htmlFor={id} className="toggle-label">
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

function SparklineSection({ bars, loading, error, errorRequestId, onRetry }) {
  const sparkMax = Math.max(...bars, 1)
  const total = bars.reduce((s, v) => s + v, 0)

  if (loading) {
    return <SidebarSkeleton rows={1} tall />
  }
  if (error) {
    return (
      <div className="sidebar-spark-error">
        <p className="sidebar-empty">
          {error}
          {errorRequestId && (
            <>
              {' '}
              (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                ref: {errorRequestId}
              </a>)
            </>
          )}
        </p>
        <button type="button" className="sidebar-retry-btn mono" onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  }
  if (bars.length === 0) {
    return <p className="sidebar-empty">Could not load publication history.</p>
  }

  return (
    <>
      <div className="sparkline" aria-label="14-day CVE publication counts">
        {bars.map((val, i) => {
          const pct = Math.max(Math.round((val / sparkMax) * 100), val === 0 ? 4 : 8)
          return (
            <div
              key={i}
              className={`spark-bar${i === bars.length - 1 ? ' spark-today' : ''}${val === 0 ? ' spark-bar-zero' : ''}`}
              style={{ height: `${pct}%` }}
              title={i === bars.length - 1 ? `Today: ${val}` : `Day ${i + 1}: ${val}`}
              aria-label={i === bars.length - 1 ? `Today: ${val} CVEs` : `${val} CVEs`}
            />
          )
        })}
      </div>
      <div className="sparkline-labels" aria-hidden="true">
        <span>14d ago</span>
        <span>today</span>
      </div>
      {total === 0 && (
        <p className="sidebar-spark-note mono">No CVEs published in the last 14 days.</p>
      )}
    </>
  )
}

export default function Sidebar({ filters, onFiltersChange }) {
  const [topTechniques, setTopTechniques] = useState([])
  const [techniquesLoading, setTechniquesLoading] = useState(true)
  const [techniquesError, setTechniquesError] = useState(null)
  const [techniquesErrorRequestId, setTechniquesErrorRequestId] = useState(null)
  const [sparkBars, setSparkBars] = useState([])
  const [sparkLoading, setSparkLoading] = useState(true)
  const [sparkError, setSparkError] = useState(null)
  const [sparkErrorRequestId, setSparkErrorRequestId] = useState(null)
  const savedStack = getSavedStack()

  const loadSparkline = useCallback((useCache = true) => {
    if (useCache) {
      const hit = getCached('spark-v2')
      if (hit !== undefined) {
        setSparkBars(hit)
        setSparkLoading(false)
        setSparkError(null)
        setSparkErrorRequestId(null)
        return
      }
    }
    let cancelled = false
    setSparkLoading(true)
    setSparkError(null)
    setSparkErrorRequestId(null)
    fetchStatsTimeline(SPARKLINE_DAYS)
      .then(data => {
        if (cancelled) return
        const bars = Array.isArray(data) && data.length ? data.map(d => d.count || 0) : []
        if (!bars.length) {
          setSparkError('Publication data unavailable — check that the backend is running.')
          setSparkBars([])
          return
        }
        setCached('spark-v2', bars)
        setSparkBars(bars)
      })
      .catch(err => {
        if (!cancelled) {
          setSparkError(err?.message || 'Could not load publications — is the backend running?')
          setSparkErrorRequestId(err?.requestId || null)
          setSparkBars([])
          notifyApiError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setSparkLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const cleanup = loadSparkline(true)
    return cleanup
  }, [loadSparkline])

  useEffect(() => {
    function onFocus() {
      loadSparkline(true)
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [loadSparkline])

  const loadTopTechniques = useCallback((useCache = true) => {
    if (useCache) {
      const hit = getCached('tech')
      if (hit !== undefined) {
        setTopTechniques(hit)
        setTechniquesLoading(false)
        setTechniquesError(null)
        setTechniquesErrorRequestId(null)
        return undefined
      }
    }
    let cancelled = false
    setTechniquesLoading(true)
    setTechniquesError(null)
    setTechniquesErrorRequestId(null)
    fetchTopTechniques(TOP_TECHNIQUES_LIMIT)
      .then(data => {
        if (cancelled) return
        const rows = data.data || []
        setCached('tech', rows)
        setTopTechniques(rows)
      })
      .catch(err => {
        if (!cancelled) {
          setTopTechniques([])
          setTechniquesError(err?.message || 'Failed to load top techniques.')
          setTechniquesErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setTechniquesLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => loadTopTechniques(true), [loadTopTechniques])

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

      {/* ── Section 1: Your Filters ── */}
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

      {/* ── Section 2: 14-day publications ── */}
      <section className="sidebar-section" aria-labelledby="sparkline-heading">
        <h2 id="sparkline-heading" className="sidebar-heading">14-DAY PUBLICATIONS</h2>
        <SparklineSection
          bars={sparkBars}
          loading={sparkLoading}
          error={sparkError}
          errorRequestId={sparkErrorRequestId}
          onRetry={() => {
            sidebarCache.delete('spark-v2')
            loadSparkline(false)
          }}
        />
      </section>

      {/* ── Section 3: Top techniques ── */}
      <section className="sidebar-section" aria-labelledby="techniques-heading">
        <h2 id="techniques-heading" className="sidebar-heading">// TOP TECHNIQUES THIS WEEK</h2>
        {techniquesLoading && <SidebarSkeleton rows={3} />}
        {!techniquesLoading && techniquesError && (
          <div className="sidebar-spark-error">
            <p className="sidebar-empty">
              {techniquesError}
              {techniquesErrorRequestId && (
                <>
                  {' '}
                  (<a href={ingestLogUrl({ level: 'ERROR', requestId: techniquesErrorRequestId })}>
                    ref: {techniquesErrorRequestId}
                  </a>)
                </>
              )}
            </p>
            <button
              type="button"
              className="sidebar-retry-btn mono"
              onClick={() => {
                sidebarCache.delete('tech')
                loadTopTechniques(false)
              }}
            >
              Retry
            </button>
          </div>
        )}
        {!techniquesLoading && !techniquesError && topTechniques.length === 0 && (
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
