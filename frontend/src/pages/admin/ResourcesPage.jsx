import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { adminApi } from '../../api.js'
import { ChartDataTable } from '../../components/ui/index.js'
import AsyncSection from './shared/AsyncSection.jsx'
import StatCard from './shared/StatCard.jsx'
import HelpTip from './shared/HelpTip.jsx'
import { AdminChartSkeleton } from './shared/AdminSkeletons.jsx'
import { fmtBytes, fmtIsoMono } from './formatters.js'

const ResourceLineChart = lazy(() =>
  import('./resourcesChartsRecharts.jsx').then((mod) => ({ default: mod.ResourceLineChart })),
)

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

function seriesHasPlottableData(series, fields) {
  if (!series?.length) return false
  return series.some(row =>
    fields.some(field => {
      const v = row[field]
      return v != null && !Number.isNaN(Number(v))
    }),
  )
}

function ResourceChartSection({ series, fields, labels, tableTitle }) {
  const hasData = seriesHasPlottableData(series, fields)

  const tableRows = useMemo(() => {
    if (!hasData) return []
    return series
      .filter((row) =>
        fields.some((field) => {
          const v = row[field]
          return v != null && !Number.isNaN(Number(v))
        }),
      )
      .slice(-48)
      .map((row, index) => {
        const entry = {
          _key: row.ts || index,
          ts: row.ts ? String(row.ts).slice(0, 19) : '—',
        }
        fields.forEach((field) => {
          entry[field] = fmtMetric(field, row[field])
        })
        return entry
      })
  }, [series, fields, hasData])

  const tableColumns = useMemo(() => {
    const cols = [{ key: 'ts', label: 'Sample (UTC)', className: 'mono' }]
    fields.forEach((field, idx) => {
      cols.push({
        key: field,
        label: labels[idx] || field,
        className: 'mono',
      })
    })
    return cols
  }, [fields, labels])

  if (!hasData) {
    return (
      <div className="admin-empty admin-ops-chart-empty" role="status">
        No samples in this window yet
      </div>
    )
  }

  return (
    <>
      <Suspense fallback={<AdminChartSkeleton height={200} />}>
        <ResourceLineChart
          series={series}
          fields={fields}
          labels={labels}
          tableTitle={tableTitle}
        />
      </Suspense>
      <ChartDataTable
        title={tableTitle || 'Resource utilization data'}
        columns={tableColumns}
        rows={tableRows}
      />
    </>
  )
}

export default function ResourcesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const windowKey = WINDOWS.includes(searchParams.get('window')) ? searchParams.get('window') : '1d'
  const [payload, setPayload] = useState(null)
  const [loadError, setLoadError] = useState(null)

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

  const series = payload?.series || []
  const summary = payload?.summary || {}
  const degraded = payload?.degraded || {}

  const chartSections = useMemo(() => ([
    {
      id: 'cpu',
      fields: ['briefr_cpu_pct', 'pg_cpu_pct'],
      labels: ['BRIEFR CPU %', 'Postgres CPU %'],
      field: 'briefr_cpu_pct',
      label: 'CPU utilization',
      tip: 'BRIEFR process tree only (uvicorn + scheduler children), not system-wide. Postgres CPU is the local postgres process tree when visible to psutil.',
    },
    {
      id: 'ram',
      fields: ['briefr_rss_bytes', 'pg_rss_bytes'],
      labels: ['BRIEFR process', 'Postgres process'],
      field: 'briefr_rss_bytes',
      label: 'Process memory',
      tip: 'Resident memory for the BRIEFR and Postgres process trees. System memory % is shown separately below.',
    },
    {
      id: 'iops',
      fields: ['briefr_iops_r', 'briefr_iops_w'],
      labels: ['BRIEFR read IOPS', 'BRIEFR write IOPS'],
      field: 'briefr_iops_r',
      label: 'Disk IOPS (BRIEFR)',
      tip: 'Read/write operations per second derived from process I/O counter deltas between samples.',
    },
    {
      id: 'req',
      fields: ['req_count'],
      labels: ['Requests / sample'],
      field: 'req_count',
      label: 'HTTP requests',
      tip: 'In-process counter read-and-reset each minute by the collector. Restarts create a ≤60s gap.',
    },
    {
      id: 'pg_xact',
      fields: ['pg_xact_per_min'],
      labels: ['PG transactions / min'],
      field: 'pg_xact_per_min',
      label: 'Postgres transactions',
      tip: 'Commits + rollbacks per minute from pg_stat_database deltas. NULL on SQLite dev.',
    },
    {
      id: 'pg_cache',
      fields: ['pg_cache_hit_pct'],
      labels: ['Cache hit %'],
      field: 'pg_cache_hit_pct',
      label: 'Postgres buffer cache hit',
      tip: 'blks_hit / (blks_hit + blks_read) over each sample interval.',
    },
    {
      id: 'disk_free',
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

      <AsyncSection data={payload} error={loadError} onRetry={load} skeletonVariant="chart">
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
                <ResourceChartSection
                  series={series}
                  fields={section.fields}
                  labels={section.labels}
                  tableTitle={section.label}
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
