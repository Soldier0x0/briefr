import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { fetchKEVDeadlines, fetchChanges, fetchCVEEpssHistory } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import { ingestLogUrl } from '../utils/adminLinks.js'
import { loadChartJs, readChartTheme } from '../utils/chartLoader.js'
import { prefersReducedMotion } from '../utils/motion.js'
import { kevBucketDateRange } from '../utils/kevDeadline.js'
import {
  buildEpssSparklinePoints,
  epssSparklinePolyline,
  EPSS_SPARKLINE_WIDTH,
  EPSS_SPARKLINE_HEIGHT,
} from '../utils/epssSparkline.js'
import TimeWindowPicker, {
  defaultPresetWindow,
  hoursFromWindow,
} from './TimeWindowPicker.jsx'
import './BriefCharts.css'

const POLL_MS = 5 * 60 * 1000
const EPSS_MOVERS_LIMIT = 10

const KEV_BUCKETS = [
  { key: 'overdue', label: 'Overdue' },
  { key: '0-7', label: '0–7d' },
  { key: '8-14', label: '8–14d' },
  { key: '15-30', label: '15–30d' },
  { key: '31+', label: '31d+' },
]

function parseDueDate(dueDate) {
  if (!dueDate) return null
  const raw = dueDate.includes('T') ? dueDate : `${dueDate}T12:00:00Z`
  const due = new Date(raw)
  return Number.isNaN(due.getTime()) ? null : due
}

function filterKevByTimeWindow(entries, window) {
  if (!window) return entries
  if (window.mode === 'custom') {
    const since = window.since ? new Date(window.since) : null
    const until = window.until ? new Date(window.until) : new Date()
    return entries.filter(row => {
      const due = parseDueDate(row.due_date)
      if (!due) return false
      if (since && due < since) return false
      if (until && due > until) return false
      return true
    })
  }
  const days = Math.max(1, Math.ceil((window.hours || 168) / 24))
  const today = new Date()
  today.setUTCHours(12, 0, 0, 0)
  const minDue = new Date(today)
  minDue.setUTCDate(minDue.getUTCDate() - days)
  const maxDue = new Date(today)
  maxDue.setUTCDate(maxDue.getUTCDate() + days)
  return entries.filter(row => {
    const due = parseDueDate(row.due_date)
    if (!due) return false
    return due >= minDue && due <= maxDue
  })
}

function windowSummaryLabel(window) {
  if (!window) return ''
  if (window.mode === 'custom') {
    const since = window.since ? shortDateLabel(window.since.slice(0, 10)) : 'any'
    const until = window.until ? shortDateLabel(window.until.slice(0, 10)) : 'now'
    return `Due dates from ${since} through ${until}`
  }
  const preset = window.presetId || `${window.hours}h`
  return `Due dates ±${preset} from today`
}

function epssDeltaClass(delta) {
  if (delta >= 0.2) return 'badge-epss-delta--high'
  if (delta >= 0.05) return 'badge-epss-delta--medium'
  return 'badge-epss-delta--low'
}

function shortDateLabel(isoDate) {
  if (!isoDate) return ''
  const d = new Date(`${isoDate}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

function daysUntilDue(dueDate) {
  if (!dueDate) return null
  const raw = dueDate.includes('T') ? dueDate : `${dueDate}T12:00:00Z`
  const due = new Date(raw)
  if (Number.isNaN(due.getTime())) return null
  const today = new Date()
  today.setUTCHours(12, 0, 0, 0)
  return Math.round((due.getTime() - today.getTime()) / 86400000)
}

function kevDueBucket(days) {
  if (days == null) return '31+'
  if (days < 0) return 'overdue'
  if (days <= 7) return '0-7'
  if (days <= 14) return '8-14'
  if (days <= 30) return '15-30'
  return '31+'
}

function buildKevHistogram(entries) {
  const counts = Object.fromEntries(KEV_BUCKETS.map(b => [b.key, 0]))
  for (const row of entries) {
    const bucket = kevDueBucket(daysUntilDue(row.due_date))
    counts[bucket] = (counts[bucket] || 0) + 1
  }
  return KEV_BUCKETS.map(b => counts[b.key] || 0)
}

function kevBucketColors(theme) {
  return [
    theme.red,
    theme.red,
    theme.amber,
    theme.textMuted,
    theme.textMuted,
  ]
}

function epssDelta(row) {
  const oldN = Number(row.old_value)
  const newN = Number(row.new_value)
  if (!Number.isFinite(oldN) || !Number.isFinite(newN)) return null
  return newN - oldN
}

function formatEpssPct(value) {
  return `${(value * 100).toFixed(1)}%`
}

function buildEpssMovers(changes) {
  const movers = []
  for (const row of changes) {
    if (row.field_name !== 'epss_score') continue
    const delta = epssDelta(row)
    if (delta == null || delta <= 0) continue
    const oldN = Number(row.old_value)
    const newN = Number(row.new_value)
    if (formatEpssPct(oldN) === formatEpssPct(newN)) continue
    movers.push({
      cve_id: row.cve_id,
      delta,
      new_score: newN,
      severity: row.severity || null,
    })
  }
  movers.sort((a, b) => b.delta - a.delta || a.cve_id.localeCompare(b.cve_id))
  return movers.slice(0, EPSS_MOVERS_LIMIT)
}

function severityDotClass(severity) {
  const s = (severity || '').toLowerCase()
  if (s === 'critical') return 'sev-dot-critical'
  if (s === 'high') return 'sev-dot-high'
  if (s === 'medium') return 'sev-dot-medium'
  if (s === 'low') return 'sev-dot-low'
  return 'sev-dot-neutral'
}

function chartAnimationOptions() {
  if (prefersReducedMotion()) {
    return { duration: 0 }
  }
  return { duration: 400 }
}

function baseOptions(theme) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: chartAnimationOptions(),
    layout: {
      padding: { left: 4, right: 8, top: 4, bottom: 4 },
    },
    plugins: {
      legend: {
        labels: {
          color: theme.textSecondary,
          font: { family: theme.mono, size: 10 },
          boxWidth: 10,
        },
      },
      tooltip: {
        backgroundColor: theme.panel,
        titleColor: theme.text,
        bodyColor: theme.textSecondary,
        borderColor: theme.grid,
        borderWidth: 1,
        titleFont: { family: theme.mono, size: 11 },
        bodyFont: { family: theme.mono, size: 11 },
      },
    },
    scales: {
      x: {
        ticks: {
          color: theme.textMuted,
          font: { family: theme.mono, size: 9 },
          maxRotation: 0,
        },
        grid: { color: theme.grid },
        border: { color: theme.grid },
      },
      y: {
        ticks: {
          color: theme.textMuted,
          font: { family: theme.mono, size: 9 },
          precision: 0,
        },
        grid: { color: theme.grid },
        border: { color: theme.grid },
        beginAtZero: true,
      },
    },
  }
}

function EpssSparklineCell({ history, currentScore }) {
  const points = buildEpssSparklinePoints(history, currentScore)
  const polyline = epssSparklinePolyline(points)
  if (!polyline) {
    return <span className="brief-epss-sparkline brief-epss-sparkline--empty" aria-hidden="true" />
  }
  return (
    <svg
      className="brief-epss-sparkline"
      width={EPSS_SPARKLINE_WIDTH}
      height={EPSS_SPARKLINE_HEIGHT}
      viewBox={`0 0 ${EPSS_SPARKLINE_WIDTH} ${EPSS_SPARKLINE_HEIGHT}`}
      role="img"
      aria-label={`EPSS trend, ${points.length} days`}
    >
      <polyline
        points={polyline}
        fill="none"
        stroke="var(--text3)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function EpssMoversTable({ movers, histories, loading, onSelectCVE, windowLabel }) {
  if (!movers.length && !loading) {
    return <p className="brief-charts-empty mono">No EPSS increases in the last {windowLabel}.</p>
  }

  return (
    <div className="brief-epss-table-wrap">
      <table className="brief-epss-table" aria-label={`Top EPSS movers in the last ${windowLabel}`}>
        <thead>
          <tr>
            <th scope="col" className="mono">CVE</th>
            <th scope="col" className="mono brief-epss-col-sev" aria-label="Severity" />
            <th scope="col" className="mono">7d trend</th>
            <th scope="col" className="mono brief-epss-col-delta">Δ</th>
          </tr>
        </thead>
        <tbody>
          {movers.map(row => {
            const history = histories[row.cve_id] || []
            return (
              <tr key={row.cve_id}>
                <td colSpan={4} className="brief-epss-row-cell">
                  <button
                    type="button"
                    className="brief-epss-row-btn"
                    onClick={() => onSelectCVE?.({ cve_id: row.cve_id })}
                    aria-label={`Open ${row.cve_id} details, EPSS increased ${(row.delta * 100).toFixed(1)} percentage points`}
                  >
                    <span className="brief-epss-id mono">{row.cve_id}</span>
                    <span className="brief-epss-sev">
                      <span
                        className={`sev-dot ${severityDotClass(row.severity)}`}
                        title={row.severity || 'Unknown severity'}
                        aria-hidden="true"
                      />
                    </span>
                    <span className="brief-epss-sparkline-cell">
                      {loading && !history.length ? (
                        <span className="brief-epss-sparkline brief-epss-sparkline--loading" aria-hidden="true" />
                      ) : (
                        <EpssSparklineCell history={history} currentScore={row.new_score} />
                      )}
                    </span>
                    <span className={`brief-epss-delta badge badge-epss-delta mono ${epssDeltaClass(row.delta)}`}>
                      +{(row.delta * 100).toFixed(1)}%
                    </span>
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function BriefCharts({ onSelectCVE, onBucketClick }) {
  const [collapsed, setCollapsed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [kevEntries, setKevEntries] = useState([])
  const [epssChanges, setEpssChanges] = useState([])
  const [epssHistories, setEpssHistories] = useState({})
  const [epssHistoryLoading, setEpssHistoryLoading] = useState(false)
  const [kevWindow, setKevWindow] = useState(() => defaultPresetWindow('30d'))
  const [epssWindow, setEpssWindow] = useState(() => defaultPresetWindow('7d'))
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)

  const kevRef = useRef(null)
  const chartsRef = useRef({ kev: null })
  const onBucketClickRef = useRef(onBucketClick)
  const lastFetchedIdsRef = useRef('')
  onBucketClickRef.current = onBucketClick

  const filteredKevEntries = useMemo(
    () => filterKevByTimeWindow(kevEntries, kevWindow),
    [kevEntries, kevWindow]
  )
  const kevHistogram = useMemo(() => buildKevHistogram(filteredKevEntries), [filteredKevEntries])
  const epssMovers = useMemo(() => buildEpssMovers(epssChanges), [epssChanges])
  const epssHours = hoursFromWindow(epssWindow)

  const loadData = useCallback(async (signal) => {
    const [kevRes, changesRes] = await Promise.allSettled([
      fetchKEVDeadlines('urgent'),
      fetchChanges({ field: 'epss_score', since_hours: epssHours, limit: 50 }),
    ])
    if (signal?.aborted) return
    if (kevRes.status === 'fulfilled') {
      setKevEntries(Array.isArray(kevRes.value?.data) ? kevRes.value.data : [])
    }
    if (changesRes.status === 'fulfilled') {
      setEpssChanges(Array.isArray(changesRes.value?.data) ? changesRes.value.data : [])
    }
    const failed = [kevRes, changesRes].find(r => r.status === 'rejected')
    if (failed) {
      setError(failed.reason?.message || 'Failed to load chart data.')
      setErrorRequestId(failed.reason?.requestId || null)
      notifyApiError(failed.reason)
    } else {
      setError(null)
      setErrorRequestId(null)
    }
  }, [epssHours])

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    setLoading(true)
    loadData(controller.signal)
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    const pollId = setInterval(() => {
      loadData(controller.signal)
    }, POLL_MS)
    return () => {
      cancelled = true
      controller.abort()
      clearInterval(pollId)
    }
  }, [loadData])

  const handleRetry = useCallback(() => {
    setLoading(true)
    loadData().finally(() => setLoading(false))
  }, [loadData])

  useEffect(() => {
    const currentIds = epssMovers.map(m => m.cve_id).join(',')

    if (!epssMovers.length) {
      lastFetchedIdsRef.current = ''
      setEpssHistories({})
      setEpssHistoryLoading(false)
      return undefined
    }

    if (currentIds === lastFetchedIdsRef.current) {
      return undefined
    }
    lastFetchedIdsRef.current = currentIds

    let cancelled = false
    setEpssHistoryLoading(true)
    Promise.allSettled(
      epssMovers.map(row =>
        fetchCVEEpssHistory(row.cve_id).then(data => ({
          cve_id: row.cve_id,
          history: Array.isArray(data) ? data : [],
        }))
      )
    )
      .then(results => {
        if (cancelled) return
        const next = {}
        for (const res of results) {
          if (res.status === 'fulfilled') {
            next[res.value.cve_id] = res.value.history
          }
        }
        setEpssHistories(next)
      })
      .finally(() => {
        if (!cancelled) setEpssHistoryLoading(false)
      })

    return () => { cancelled = true }
  }, [epssMovers])

  useEffect(() => {
    if (collapsed || loading) return undefined

    let cancelled = false
    let Chart = null

    async function renderKevChart() {
      Chart = await loadChartJs()
      if (cancelled || !kevRef.current) return

      const theme = readChartTheme()
      const shared = baseOptions(theme)

      chartsRef.current.kev?.destroy()
      chartsRef.current.kev = new Chart(kevRef.current, {
        type: 'bar',
        data: {
          labels: KEV_BUCKETS.map(b => b.label),
          datasets: [
            {
              label: 'KEV entries',
              data: kevHistogram,
              backgroundColor: kevBucketColors(theme),
              borderWidth: 0,
              borderRadius: 0,
            },
          ],
        },
        options: {
          ...shared,
          plugins: {
            ...shared.plugins,
            legend: { display: false },
            tooltip: {
              ...shared.plugins.tooltip,
              callbacks: {
                afterLabel(ctx) {
                  const bucket = KEV_BUCKETS[ctx.dataIndex]
                  if (!bucket) return ''
                  const range = kevBucketDateRange(bucket.key)
                  const start = range.start ? shortDateLabel(range.start) : 'any'
                  const end = range.end ? shortDateLabel(range.end) : 'any'
                  return `Due ${start} – ${end}`
                },
              },
            },
          },
          onClick(_event, elements) {
            if (!elements.length) return
            const bucket = KEV_BUCKETS[elements[0].index]
            if (!bucket) return
            onBucketClickRef.current?.(kevBucketDateRange(bucket.key))
          },
          onHover(event, elements) {
            const target = event.native?.target
            if (target) {
              target.style.cursor = elements.length ? 'pointer' : 'default'
            }
          },
        },
      })
    }

    renderKevChart().catch(() => {})

    return () => {
      cancelled = true
      chartsRef.current.kev?.destroy()
      chartsRef.current.kev = null
    }
  }, [collapsed, loading, kevHistogram])

  const hasData = filteredKevEntries.length > 0 || epssMovers.length > 0

  return (
    <section
      className={`brief-charts${collapsed ? ' brief-charts--collapsed' : ''}`}
      aria-label="Analyst brief charts"
    >
      <div className="brief-charts-header">
        <button
          type="button"
          className="brief-charts-toggle"
          onClick={() => setCollapsed(c => !c)}
          aria-expanded={!collapsed}
          aria-controls="brief-charts-body"
          aria-label={collapsed ? 'Expand analyst charts' : 'Collapse analyst charts'}
        >
          <span className={`brief-charts-chevron${collapsed ? ' collapsed' : ''}`} aria-hidden="true">
            ▾
          </span>
        </button>
        <h2 className="brief-charts-title mono">// ANALYST CHARTS</h2>
      </div>

      {!collapsed && (
        <div id="brief-charts-body" className="brief-charts-body">
          {loading ? (
            <p className="brief-charts-loading mono" aria-live="polite">
              Loading charts…
            </p>
          ) : error && !hasData ? (
            <div className="brief-charts-error mono" role="alert">
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
              <button type="button" className="brief-charts-retry-btn" onClick={handleRetry}>
                Retry
              </button>
            </div>
          ) : !hasData ? (
            <p className="brief-charts-empty mono">No chart data yet — wait for ingest.</p>
          ) : (
            <>
              {error && (
                <div className="brief-charts-error mono brief-charts-error--partial" role="alert">
                  <span>
                    Some chart data failed to load: {error}
                    {errorRequestId && (
                      <>
                        {' '}
                        (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                          ref: {errorRequestId}
                        </a>)
                      </>
                    )}
                  </span>
                  <button type="button" className="brief-charts-retry-btn" onClick={handleRetry}>
                    Retry
                  </button>
                </div>
              )}
              <div className="brief-charts-grid">
              <article className="brief-chart-card" aria-label="KEV due-date histogram">
                <div className="brief-chart-card-head">
                  <h3 className="brief-chart-card-title">KEV DUE DATES</h3>
                  <TimeWindowPicker
                    value={kevWindow}
                    onChange={setKevWindow}
                    ariaLabel="KEV due date window"
                    presetIds={['6h', '12h', '24h', '2d', '7d', '30d', '90d']}
                  />
                </div>
                <p className="brief-chart-card-hint mono">{windowSummaryLabel(kevWindow)}</p>
                <div className="brief-chart-canvas-wrap brief-chart-canvas-wrap--kev">
                  <canvas ref={kevRef} role="img" aria-label="KEV remediation deadline histogram" />
                </div>
              </article>
              <article className="brief-chart-card brief-chart-card--table" aria-label="Top EPSS movers">
                <div className="brief-chart-card-head">
                  <h3 className="brief-chart-card-title">TOP EPSS MOVERS</h3>
                  <TimeWindowPicker
                    value={epssWindow}
                    onChange={setEpssWindow}
                    ariaLabel="EPSS change window"
                  />
                </div>
                <EpssMoversTable
                  movers={epssMovers}
                  histories={epssHistories}
                  loading={epssHistoryLoading}
                  onSelectCVE={onSelectCVE}
                  windowLabel={epssWindow.mode === 'custom'
                    ? 'selected range'
                    : (epssWindow.presetId || `${epssHours}h`)}
                />
              </article>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  )
}
