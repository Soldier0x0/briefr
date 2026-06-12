import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { fetchStatsTimeline, fetchKEVDeadlines, fetchChanges } from '../api.js'
import { loadChartJs, readChartTheme } from '../utils/chartLoader.js'
import { prefersReducedMotion } from '../utils/motion.js'
import './BriefCharts.css'

const TIMELINE_DAYS = 30
const POLL_MS = 5 * 60 * 1000
const EPSS_WINDOW_HOURS = 168
const EPSS_MOVERS_LIMIT = 10

const KEV_BUCKETS = [
  { key: 'overdue', label: 'Overdue' },
  { key: '0-7', label: '0–7d' },
  { key: '8-14', label: '8–14d' },
  { key: '15-30', label: '15–30d' },
  { key: '31+', label: '31d+' },
]

function shortDateLabel(isoDate) {
  const d = new Date(`${isoDate}T12:00:00Z`)
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
    })
  }
  movers.sort((a, b) => b.delta - a.delta || a.cve_id.localeCompare(b.cve_id))
  return movers.slice(0, EPSS_MOVERS_LIMIT)
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
    plugins: {
      legend: {
        labels: {
          color: theme.text,
          font: { family: theme.mono, size: 10 },
          boxWidth: 10,
        },
      },
      tooltip: {
        titleFont: { family: theme.mono, size: 11 },
        bodyFont: { family: theme.mono, size: 11 },
      },
    },
    scales: {
      x: {
        ticks: { color: theme.textMuted, font: { family: theme.mono, size: 9 }, maxRotation: 0 },
        grid: { color: theme.grid },
        border: { color: theme.grid },
      },
      y: {
        ticks: { color: theme.textMuted, font: { family: theme.mono, size: 9 } },
        grid: { color: theme.grid },
        border: { color: theme.grid },
        beginAtZero: true,
      },
    },
  }
}

export default function BriefCharts() {
  const [collapsed, setCollapsed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [timeline, setTimeline] = useState([])
  const [kevEntries, setKevEntries] = useState([])
  const [epssChanges, setEpssChanges] = useState([])

  const timelineRef = useRef(null)
  const kevRef = useRef(null)
  const epssRef = useRef(null)
  const chartsRef = useRef({ timeline: null, kev: null, epss: null })

  const slicedTimeline = useMemo(() => {
    if (!timeline.length) return []
    if (timeline.length <= TIMELINE_DAYS) return timeline
    return timeline.slice(-TIMELINE_DAYS)
  }, [timeline])

  const kevHistogram = useMemo(() => buildKevHistogram(kevEntries), [kevEntries])
  const epssMovers = useMemo(() => buildEpssMovers(epssChanges), [epssChanges])

  const loadData = useCallback(async (signal) => {
    const [timelineRes, kevRes, changesRes] = await Promise.allSettled([
      fetchStatsTimeline(TIMELINE_DAYS),
      fetchKEVDeadlines('urgent'),
      fetchChanges({ field: 'epss_score', sinceHours: EPSS_WINDOW_HOURS, limit: 50 }),
    ])
    if (signal?.aborted) return
    if (timelineRes.status === 'fulfilled') {
      setTimeline(Array.isArray(timelineRes.value) ? timelineRes.value : [])
    }
    if (kevRes.status === 'fulfilled') {
      setKevEntries(Array.isArray(kevRes.value?.data) ? kevRes.value.data : [])
    }
    if (changesRes.status === 'fulfilled') {
      setEpssChanges(Array.isArray(changesRes.value?.data) ? changesRes.value.data : [])
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    setLoading(true)
    loadData(controller.signal)
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    const pollId = setInterval(() => {
      loadData(controller.signal).catch(() => {})
    }, POLL_MS)
    return () => {
      cancelled = true
      controller.abort()
      clearInterval(pollId)
    }
  }, [loadData])

  useEffect(() => {
    if (collapsed || loading) return undefined

    let cancelled = false
    let Chart = null

    async function renderCharts() {
      Chart = await loadChartJs()
      if (cancelled) return

      const theme = readChartTheme()
      const shared = baseOptions(theme)

      if (timelineRef.current) {
        chartsRef.current.timeline?.destroy()
        const labels = slicedTimeline.map(row => shortDateLabel(row.date))
        chartsRef.current.timeline = new Chart(timelineRef.current, {
          type: 'line',
          data: {
            labels,
            datasets: [
              {
                label: 'Total',
                data: slicedTimeline.map(row => row.count || 0),
                borderColor: theme.accent,
                backgroundColor: `${theme.accent}33`,
                fill: true,
                tension: 0.25,
                pointRadius: 0,
                borderWidth: 1.5,
              },
              {
                label: 'Critical',
                data: slicedTimeline.map(row => row.critical || 0),
                borderColor: theme.red,
                backgroundColor: 'transparent',
                tension: 0.25,
                pointRadius: 0,
                borderWidth: 1.5,
              },
            ],
          },
          options: {
            ...shared,
            interaction: { mode: 'index', intersect: false },
            plugins: {
              ...shared.plugins,
              legend: { ...shared.plugins.legend, position: 'top' },
            },
          },
        })
      }

      if (kevRef.current) {
        chartsRef.current.kev?.destroy()
        chartsRef.current.kev = new Chart(kevRef.current, {
          type: 'bar',
          data: {
            labels: KEV_BUCKETS.map(b => b.label),
            datasets: [
              {
                label: 'KEV entries',
                data: kevHistogram,
                backgroundColor: [
                  theme.red,
                  theme.amber,
                  theme.amber,
                  theme.accent,
                  theme.textMuted,
                ],
                borderWidth: 0,
              },
            ],
          },
          options: {
            ...shared,
            plugins: {
              ...shared.plugins,
              legend: { display: false },
            },
          },
        })
      }

      if (epssRef.current) {
        chartsRef.current.epss?.destroy()
        const labels = epssMovers.map(row => row.cve_id.replace('CVE-', ''))
        chartsRef.current.epss = new Chart(epssRef.current, {
          type: 'bar',
          data: {
            labels,
            datasets: [
              {
                label: 'EPSS Δ (7d)',
                data: epssMovers.map(row => Math.round(row.delta * 1000) / 10),
                backgroundColor: theme.green,
                borderWidth: 0,
              },
            ],
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
                  label(ctx) {
                    const mover = epssMovers[ctx.dataIndex]
                    if (!mover) return ''
                    return `+${(mover.delta * 100).toFixed(1)} pp → ${formatEpssPct(mover.new_score)}`
                  },
                },
              },
            },
            scales: {
              x: {
                ...shared.scales.x,
                title: {
                  display: true,
                  text: 'Δ percentage points',
                  color: theme.textMuted,
                  font: { family: theme.mono, size: 9 },
                },
              },
              y: {
                ...shared.scales.y,
                ticks: {
                  ...shared.scales.y.ticks,
                  autoSkip: false,
                },
              },
            },
          },
        })
      }
    }

    renderCharts().catch(() => {})

    return () => {
      cancelled = true
      for (const key of Object.keys(chartsRef.current)) {
        chartsRef.current[key]?.destroy()
        chartsRef.current[key] = null
      }
    }
  }, [collapsed, loading, slicedTimeline, kevHistogram, epssMovers])

  const hasData = slicedTimeline.length > 0 || kevEntries.length > 0 || epssMovers.length > 0

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
          ) : !hasData ? (
            <p className="brief-charts-empty mono">No chart data yet — wait for ingest.</p>
          ) : (
            <div className="brief-charts-grid">
              <article className="brief-chart-card" aria-label="Severity and volume timeline">
                <h3 className="brief-chart-card-title">SEVERITY / VOLUME ({TIMELINE_DAYS}D)</h3>
                <div className="brief-chart-canvas-wrap">
                  <canvas ref={timelineRef} role="img" aria-label="CVE publication timeline" />
                </div>
              </article>
              <article className="brief-chart-card" aria-label="KEV due-date histogram">
                <h3 className="brief-chart-card-title">KEV DUE DATES</h3>
                <div className="brief-chart-canvas-wrap">
                  <canvas ref={kevRef} role="img" aria-label="KEV remediation deadline histogram" />
                </div>
              </article>
              <article className="brief-chart-card" aria-label="Top EPSS movers">
                <h3 className="brief-chart-card-title">TOP EPSS MOVERS (7D)</h3>
                <div className="brief-chart-canvas-wrap">
                  <canvas
                    ref={epssRef}
                    role="img"
                    aria-label="Largest EPSS score increases in the last seven days"
                  />
                </div>
              </article>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
