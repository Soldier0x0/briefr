import { useState, useEffect, useRef, useMemo } from 'react'
import { fetchTopVendors, fetchChanges, fetchCVEEpssHistory } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import useAsync from '../hooks/useAsync.js'
import useVisibilityAwareInterval from '../hooks/useVisibilityAwareInterval.js'
import { AsyncState, ErrorState, Skeleton } from './ui/index.js'
import { loadChartJs, readChartTheme } from '../utils/chartLoader.js'
import { axisTitle, baseChartOptions } from '../utils/chartOptions.js'
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
const TOP_VENDOR_LIMIT = 10
// Stable reference so `data?.field ?? EMPTY_ARRAY` doesn't recreate a new
// array every render while `data` is still null (useAsync's initial/loading
// state) — a fresh `[]` there would retrigger the useMemo/useEffect below on
// every render and never converge (#loop).
const EMPTY_ARRAY = []

function epssDeltaClass(delta) {
  if (delta >= 0.2) return 'badge-epss-delta--high'
  if (delta >= 0.05) return 'badge-epss-delta--medium'
  return 'badge-epss-delta--low'
}

function shortVendorLabel(name) {
  if (!name) return 'Unknown'
  return name.length > 28 ? `${name.slice(0, 28)}…` : name
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

export default function BriefCharts({ onSelectCVE, pollEnabled = true }) {
  const [collapsed, setCollapsed] = useState(false)
  const [epssHistories, setEpssHistories] = useState({})
  const [epssHistoryLoading, setEpssHistoryLoading] = useState(false)
  const [epssWindow, setEpssWindow] = useState(() => defaultPresetWindow('7d'))

  const vendorRef = useRef(null)
  const chartsRef = useRef({ vendor: null })
  const lastFetchedIdsRef = useRef('')

  const epssHours = hoursFromWindow(epssWindow)

  const { data, error, loading, refreshing, retry } = useAsync(async (signal) => {
    const [vendorRes, changesRes] = await Promise.allSettled([
      fetchTopVendors(TOP_VENDOR_LIMIT),
      fetchChanges({ field: 'epss_score', since_hours: epssHours, limit: 50 }),
    ])
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')

    const vendorPayload = vendorRes.status === 'fulfilled' ? vendorRes.value : null
    const vendorRows = Array.isArray(vendorPayload?.data) ? vendorPayload.data : []
    const totalKev = Number(vendorPayload?.total_kev) || 0
    const epssChanges = changesRes.status === 'fulfilled' && Array.isArray(changesRes.value?.data)
      ? changesRes.value.data
      : []

    const failed = [vendorRes, changesRes].find(r => r.status === 'rejected')
    if (failed) {
      notifyApiError(failed.reason)
      const reason = failed.reason
      const err = reason instanceof Error
        ? reason
        : Object.assign(new Error(reason?.message || 'Failed to load chart data.'), {
            requestId: reason?.requestId ?? null,
          })
      const hasAny = vendorRows.length > 0 || buildEpssMovers(epssChanges).length > 0
      if (!hasAny) throw err
      return { vendorRows, totalKev, epssChanges, partialError: err }
    }

    return { vendorRows, totalKev, epssChanges, partialError: null }
  }, [epssHours])

  useVisibilityAwareInterval(retry, POLL_MS, { enabled: pollEnabled })

  const vendorRows = data?.vendorRows ?? EMPTY_ARRAY
  const totalKev = data?.totalKev ?? 0
  const epssChanges = data?.epssChanges ?? EMPTY_ARRAY
  const partialError = data?.partialError ?? null

  const epssMovers = useMemo(() => buildEpssMovers(epssChanges), [epssChanges])

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
    if (collapsed || loading || !vendorRows.length) return undefined

    let cancelled = false

    async function renderVendorChart() {
      const Chart = await loadChartJs()
      if (cancelled || !vendorRef.current) return

      const theme = readChartTheme()
      const shared = baseChartOptions(theme, { animationDuration: 400, maxRotation: 0 })

      chartsRef.current.vendor?.destroy()
      chartsRef.current.vendor = new Chart(vendorRef.current, {
        type: 'bar',
        data: {
          labels: vendorRows.map(row => shortVendorLabel(row.vendor)),
          datasets: [{
            label: 'KEV entries',
            data: vendorRows.map(row => row.kev_count),
            backgroundColor: theme.accent,
            borderWidth: 0,
            borderRadius: 0,
          }],
        },
        options: {
          ...shared,
          indexAxis: 'y',
          plugins: {
            ...shared.plugins,
            legend: { display: false },
            tooltip: {
              ...shared.plugins.tooltip,
              callbacks: {
                title(ctx) {
                  const row = vendorRows[ctx[0]?.dataIndex]
                  return row?.vendor || ctx[0]?.label || ''
                },
                label(ctx) {
                  const count = ctx.parsed.x
                  return `${count} KEV ${count === 1 ? 'entry' : 'entries'}`
                },
              },
            },
          },
          scales: {
            x: {
              ...shared.scales.x,
              ticks: {
                ...shared.scales.x.ticks,
                precision: 0,
              },
              title: axisTitle(theme, 'KEV count'),
            },
            y: {
              ...shared.scales.y,
              ticks: {
                ...shared.scales.y.ticks,
                autoSkip: false,
                maxRotation: 0,
                minRotation: 0,
              },
            },
          },
        },
      })
    }

    renderVendorChart().catch(() => {})

    return () => {
      cancelled = true
      chartsRef.current.vendor?.destroy()
      chartsRef.current.vendor = null
    }
  }, [collapsed, loading, vendorRows])

  const hasData = vendorRows.length > 0 || epssMovers.length > 0

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
          <AsyncState
            loading={loading}
            refreshing={refreshing}
            error={error}
            onRetry={retry}
            empty={!hasData}
            emptyTitle="No chart data yet — wait for ingest."
            skeleton={<Skeleton variant="text" className="brief-charts-skeleton" />}
          >
            {() => (
              <>
                {partialError && (
                  <ErrorState
                    error={partialError}
                    onRetry={retry}
                    compact
                    className="brief-charts-error--partial"
                  />
                )}
                <div className="brief-charts-grid">
              <article className="brief-chart-card" aria-label="Top KEV vendors">
                <div className="brief-chart-card-head">
                  <h3 className="brief-chart-card-title">TOP KEV VENDORS</h3>
                </div>
                <p className="brief-chart-card-hint mono">
                  {totalKev > 0
                    ? `${totalKev} catalogued KEV ${totalKev === 1 ? 'entry' : 'entries'} grouped by vendor`
                    : 'No KEV catalog entries yet — wait for ingest.'}
                </p>
                {vendorRows.length === 0 ? (
                  <div className="brief-chart-empty mono">No vendor breakdown available</div>
                ) : (
                  <div className="brief-chart-canvas-wrap brief-chart-canvas-wrap--kev">
                    <canvas ref={vendorRef} role="img" aria-label="Top KEV vendors by entry count" />
                  </div>
                )}
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
          </AsyncState>
        </div>
      )}
    </section>
  )
}
