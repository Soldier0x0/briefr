import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { adminApi } from '../../api.js'
import AsyncSection from './shared/AsyncSection.jsx'
import StatCard from './shared/StatCard.jsx'
import HelpTip from './shared/HelpTip.jsx'
import { loadChartJs, readChartTheme } from '../../utils/chartLoader.js'
import { baseChartOptions } from '../../utils/chartOptions.js'
import { fmtBytes, fmtIsoMono } from './formatters.js'

const WINDOWS = ['1d', '3d', '7d', '30d']

function fmtMetric(field, value) {
  if (value == null || Number.isNaN(value)) return '—'
  if (field.endsWith('_bytes')) return fmtBytes(value)
  if (field.endsWith('_pct')) return `${Number(value).toFixed(1)}%`
  if (field === 'req_count') return String(Math.round(value))
  if (field.includes('iops') || field.includes('_per_min') || field.includes('_bps')) {
    return Number(value).toFixed(1)
  }
  return Number(value).toFixed(2)
}

function summaryCards(summary, field, label, tip) {
  const s = summary?.[field] || {}
  return (
    <div className="admin-resources-summary-row" key={field}>
      <div className="admin-resources-summary-label">
        {label}
        <HelpTip text={tip} />
      </div>
      <div className="admin-resources-summary-cards">
        <StatCard label="Peak" value={fmtMetric(field, s.peak)} subLabel={s.peak_at ? fmtIsoMono(s.peak_at) : null} />
        <StatCard label="Average" value={fmtMetric(field, s.avg)} />
        <StatCard label="Low" value={fmtMetric(field, s.low)} />
      </div>
    </div>
  )
}

function ResourceLineChart({ id, series, fields, labels, canvasRef, chartsRef }) {
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!canvasRef.current || !series?.length) return
      const Chart = await loadChartJs()
      if (cancelled) return
      const theme = readChartTheme()
      const shared = baseChartOptions(theme)
      chartsRef.current[id]?.destroy()
      const datasets = fields.map((field, idx) => ({
        label: labels[idx],
        data: series.map(row => row[field]),
        borderColor: idx === 0 ? theme.accent : theme.text2,
        backgroundColor: 'transparent',
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 1.5,
      }))
      chartsRef.current[id] = new Chart(canvasRef.current, {
        type: 'line',
        data: {
          labels: series.map(row => row.ts?.slice(11, 16) || ''),
          datasets,
        },
        options: {
          ...shared,
          scales: {
            x: { ...shared.scales?.x, ticks: { maxTicksLimit: 8 } },
            y: { ...shared.scales?.y, beginAtZero: true },
          },
        },
      })
    })()
    return () => { cancelled = true }
  }, [series, fields, labels, id, canvasRef, chartsRef])
  return <canvas ref={canvasRef} height={120} aria-hidden="true" />
}

export default function ResourcesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const windowKey = WINDOWS.includes(searchParams.get('window')) ? searchParams.get('window') : '1d'
  const [payload, setPayload] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const chartsRef = useRef({})
  const cpuRef = useRef(null)
  const ramRef = useRef(null)
  const iopsRef = useRef(null)
  const reqRef = useRef(null)
  const pgRef = useRef(null)
  const cacheRef = useRef(null)
  const diskRef = useRef(null)

  const setWindow = useCallback((next) => {
    const params = new URLSearchParams(searchParams)
    params.set('p', 'resources')
    params.set('window', next)
    setSearchParams(params, { replace: true })
  }, [searchParams, setSearchParams])

  const load = useCallback(async () => {
    try {
      const res = await adminApi.get(`/resources?window=${windowKey}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setPayload(await res.json())
      setLoadError(null)
    } catch (e) {
      setLoadError(e)
    }
  }, [windowKey])

  useEffect(() => { load() }, [load])

  useEffect(() => () => {
    Object.values(chartsRef.current).forEach(c => c?.destroy?.())
  }, [])

  const series = payload?.series || []
  const summary = payload?.summary || {}
  const degraded = payload?.degraded || {}

  const chartSections = useMemo(() => ([
    {
      id: 'cpu',
      ref: cpuRef,
      fields: ['briefr_cpu_pct', 'pg_cpu_pct'],
      labels: ['BRIEFR CPU %', 'Postgres CPU %'],
      field: 'briefr_cpu_pct',
      label: 'CPU utilization',
      tip: 'BRIEFR process tree only (uvicorn + scheduler children), not system-wide. Postgres CPU is the local postgres process tree when visible to psutil.',
    },
    {
      id: 'ram',
      ref: ramRef,
      fields: ['briefr_rss_bytes', 'pg_rss_bytes'],
      labels: ['BRIEFR RSS', 'Postgres RSS'],
      field: 'briefr_rss_bytes',
      label: 'Memory (RSS)',
      tip: 'Resident set size for the BRIEFR and Postgres process trees. SYS memory % is shown separately below.',
    },
    {
      id: 'iops',
      ref: iopsRef,
      fields: ['briefr_iops_r', 'briefr_iops_w'],
      labels: ['BRIEFR read IOPS', 'BRIEFR write IOPS'],
      field: 'briefr_iops_r',
      label: 'Disk IOPS (BRIEFR)',
      tip: 'Read/write operations per second derived from process I/O counter deltas between samples.',
    },
    {
      id: 'req',
      ref: reqRef,
      fields: ['req_count'],
      labels: ['Requests / sample'],
      field: 'req_count',
      label: 'HTTP requests',
      tip: 'In-process counter read-and-reset each minute by the collector. Restarts create a ≤60s gap.',
    },
    {
      id: 'pg_xact',
      ref: pgRef,
      fields: ['pg_xact_per_min'],
      labels: ['PG transactions / min'],
      field: 'pg_xact_per_min',
      label: 'Postgres transactions',
      tip: 'Commits + rollbacks per minute from pg_stat_database deltas. NULL on SQLite dev.',
    },
    {
      id: 'pg_cache',
      ref: cacheRef,
      fields: ['pg_cache_hit_pct'],
      labels: ['Cache hit %'],
      field: 'pg_cache_hit_pct',
      label: 'Postgres buffer cache hit',
      tip: 'blks_hit / (blks_hit + blks_read) over each sample interval.',
    },
    {
      id: 'disk_free',
      ref: diskRef,
      fields: ['disk_free_bytes'],
      labels: ['Free bytes'],
      field: 'disk_free_bytes',
      label: 'Disk free (data volume)',
      tip: 'Free space on the filesystem hosting the database files.',
    },
  ]), [])

  return (
    <div className="admin-resources-page">
      <h1 className="admin-page-title">Resources</h1>
      <p className="admin-page-subtitle">
        BRIEFR and PostgreSQL utilization sampled every minute. Peaks and averages are computed over raw rows in the selected window.
      </p>

      <div className="admin-resources-window-row">
        {WINDOWS.map(w => (
          <button
            key={w}
            type="button"
            className={`admin-resources-window-btn mono${windowKey === w ? ' admin-resources-window-btn-active' : ''}`}
            onClick={() => setWindow(w)}
            aria-pressed={windowKey === w}
          >
            {w.toUpperCase()}
          </button>
        ))}
      </div>

      <AsyncSection data={payload} error={loadError} onRetry={load}>
        {() => (
          <>
            {degraded?.code && degraded.code !== 'ok' && (
              <div className={`intel-banner intel-banner-${degraded.code === 'empty' ? 'amber' : 'amber'}`} role="status">
                <span>{degraded.message}</span>
              </div>
            )}
            {payload?.sample_count > 0 && payload.sample_count < 60 && degraded.code === 'ok' && (
              <div className="intel-banner intel-banner-amber" role="status">
                <span>Collecting baseline samples — charts improve after about an hour of data.</span>
              </div>
            )}

            {chartSections.map(section => (
              <div className="admin-card admin-resources-chart-card" key={section.id}>
                {summaryCards(summary, section.field, section.label, section.tip)}
                <ResourceLineChart
                  id={section.id}
                  series={series}
                  fields={section.fields}
                  labels={section.labels}
                  canvasRef={section.ref}
                  chartsRef={chartsRef}
                />
              </div>
            ))}

            <div className="admin-card">
              <div className="admin-card-title">System context</div>
              {summaryCards(summary, 'sys_cpu_pct', 'Host CPU %', 'Total system CPU utilization for context alongside the BRIEFR process tree.')}
              {summaryCards(summary, 'sys_mem_pct', 'Host memory %', 'Total system memory used — helps spot contention from other software on the box.')}
            </div>
          </>
        )}
      </AsyncSection>
    </div>
  )
}
