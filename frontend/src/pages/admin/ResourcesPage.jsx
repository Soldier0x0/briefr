import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { adminApi } from '../../api.js'
import { ChartDataTable } from '../../components/ui/index.js'
import AsyncSection from './shared/AsyncSection.jsx'
import StatCard from './shared/StatCard.jsx'
import HelpTip from './shared/HelpTip.jsx'
import DiffReviewModal from './shared/DiffReviewModal.jsx'
import { AdminChartSkeleton } from './shared/AdminSkeletons.jsx'
import { fmtBytes, fmtIsoMono, diskBarColor } from './formatters.js'
import { notifyBackendRestarting } from '../../utils/backendRestart.js'

const ResourceLineChart = lazy(() =>
  import('./resourcesChartsRecharts.jsx').then((mod) => ({ default: mod.ResourceLineChart })),
)

const WINDOWS = ['1d', '3d', '7d', '30d']

function fmtSavings(rec) {
  const parts = []
  const est = rec?.estimated_savings || {}
  if (est.bytes) parts.push(`~${fmtBytes(est.bytes)} disk`)
  if (est.rows) parts.push(`~${Number(est.rows).toLocaleString()} fewer rows`)
  if (est.requests_per_day) parts.push(`~${Number(est.requests_per_day).toLocaleString()} fewer API writes/day`)
  return parts.length ? parts.join(' · ') : null
}

function SubsystemTable({ rows }) {
  if (!rows?.length) return <p className="admin-empty">No subsystem data</p>
  return (
    <table className="metering-table admin-efficiency-subsystems">
      <thead>
        <tr>
          <th scope="col">Subsystem</th>
          <th scope="col">Size</th>
          <th scope="col">Rows</th>
          <th scope="col">API / day</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.label}</td>
            <td className="mono">{row.bytes != null ? fmtBytes(row.bytes) : '—'}</td>
            <td className="mono">{row.rows != null ? Number(row.rows).toLocaleString() : '—'}</td>
            <td className="mono">{row.requests_per_day != null ? Number(row.requests_per_day).toLocaleString() : '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function RecommendationRow({ rec, onApply }) {
  const savings = fmtSavings(rec)
  const severity = rec.severity || 'info'
  return (
    <div className={`admin-efficiency-rec admin-efficiency-rec-${severity}`}>
      <div className="admin-efficiency-rec-title">{rec.title}</div>
      <p className="admin-efficiency-rec-desc">{rec.description}</p>
      {savings && <p className="mono admin-efficiency-rec-savings">{savings}</p>}
      {rec.config_key && rec.suggested_value != null && (
        <button
          type="button"
          className="admin-btn admin-btn-ghost admin-efficiency-apply"
          onClick={() => onApply(rec.config_key, rec.suggested_value)}
        >
          Apply {rec.config_key} = {rec.suggested_value}
        </button>
      )}
    </div>
  )
}

function EfficiencyPanel({ report, onApplyConfig }) {
  if (!report) return null
  return (
    <div className="admin-card admin-efficiency-panel">
      <div className="admin-card-title">
        Efficiency recommendations
        <HelpTip text="Live analysis of disk, memory, DB, and API overhead. Suggestions preserve functionality — review before applying." />
      </div>
      <SubsystemTable rows={report.subsystems} />
      {report.recommendations?.length > 0 ? (
        <div className="admin-efficiency-rec-list">
          {report.recommendations.map((rec) => (
            <RecommendationRow key={rec.id} rec={rec} onApply={onApplyConfig} />
          ))}
        </div>
      ) : (
        <p className="admin-empty" role="status">No recommendations — footprint looks healthy.</p>
      )}
    </div>
  )
}

function CapacityBar({ label, used, total, sub }) {
  const pct = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0
  return (
    <div className="admin-capacity-bar-wrap">
      <div className="admin-capacity-bar-header">
        <span>{label}</span>
        <span className="mono">{fmtBytes(used)} / {fmtBytes(total)} ({pct}%)</span>
      </div>
      <div className="disk-bar">
        <div className={`disk-bar-fill disk-bar-fill-${diskBarColor(pct)}`} style={{ width: `${pct}%` }} />
      </div>
      {sub && <p className="admin-capacity-bar-sub mono">{sub}</p>}
    </div>
  )
}

function HostCapacityCard({ profile }) {
  if (!profile?.memory_total_bytes) return null
  const memUsed = profile.memory_total_bytes - profile.memory_available_bytes
  return (
    <div className="admin-card admin-host-capacity">
      <div className="admin-card-title">
        Host capacity
        <HelpTip text="Live hardware limits from this server (psutil). Consumption includes all processes on the host, not only BRIEFR." />
      </div>
      <CapacityBar
        label="Memory"
        used={memUsed}
        total={profile.memory_total_bytes}
      />
      <CapacityBar
        label="Disk (DB volume)"
        used={profile.disk_used_bytes}
        total={profile.disk_total_bytes}
        sub={profile.disk_path}
      />
      <p className="mono admin-host-meta">
        {profile.hostname} · {profile.cpu_count_logical} logical CPUs
      </p>
    </div>
  )
}

function PoolStatsCard({ poolStats }) {
  if (!poolStats?.size) return null
  const inUse = poolStats.in_use ?? 0
  const size = poolStats.max ?? poolStats.size
  const pct = size > 0 ? Math.min(100, Math.round((inUse / size) * 100)) : 0
  return (
    <div className="admin-card admin-pool-stats">
      <div className="admin-card-title">
        Connection pool
        <HelpTip text="PostgreSQL asyncpg pool counters. SQLite dev mode has no pool." />
      </div>
      <CapacityBar label="Connections in use" used={inUse} total={size} />
      <p className="mono admin-host-meta">{inUse} in use · {poolStats.idle ?? 0} idle · max {size}</p>
    </div>
  )
}

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

function ResourceChartSection({ series, fields, labels, tableTitle, hostProfile }) {
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
      .slice()
      .reverse()
      .slice(0, 48)
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
          hostProfile={hostProfile}
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

export default function ResourcesPage({ toast, active = true }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const windowKey = WINDOWS.includes(searchParams.get('window')) ? searchParams.get('window') : '1d'
  const [payload, setPayload] = useState(null)
  const [efficiency, setEfficiency] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [pendingConfig, setPendingConfig] = useState(null)
  const [applyingConfig, setApplyingConfig] = useState(false)

  const setWindow = useCallback((next) => {
    const params = new URLSearchParams(searchParams)
    params.set('p', 'resources')
    params.set('window', next)
    setSearchParams(params, { replace: true })
  }, [searchParams, setSearchParams])

  const load = useCallback(async () => {
    if (!active) return
    try {
      const [res, effRes] = await Promise.all([
        adminApi.get(`/resources?window=${windowKey}`),
        adminApi.get('/resources/efficiency'),
      ])
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setPayload(await res.json())
      if (effRes.ok) setEfficiency(await effRes.json())
      setLoadError(null)
    } catch (e) {
      setLoadError(e)
    }
  }, [windowKey, active])

  useEffect(() => { load() }, [load])

  function applyConfig(key, value) {
    setPendingConfig({ [key]: String(value) })
  }

  async function confirmApplyConfig() {
    if (!pendingConfig) return
    setApplyingConfig(true)
    try {
      const body = Object.entries(pendingConfig).map(([key, value]) => ({ key, value }))
      const { data } = await adminApi.postJson('/config/apply-all', body)
      if (data?.restart_required ?? data?.warning_restart_required) {
        notifyBackendRestarting()
      }
      toast?.(data?.message || 'Configuration applied', true)
      setPendingConfig(null)
      load()
    } catch (e) {
      toast?.(e?.message || 'Apply failed', false)
    } finally {
      setApplyingConfig(false)
    }
  }

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
      {pendingConfig && (
        <DiffReviewModal
          title="Apply efficiency recommendation"
          changes={pendingConfig}
          applying={applyingConfig}
          applyLabel="Apply change"
          onApply={confirmApplyConfig}
          onDiscard={() => setPendingConfig(null)}
          onClose={() => setPendingConfig(null)}
        />
      )}
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

            <HostCapacityCard profile={payload?.host_profile} />
            <PoolStatsCard poolStats={payload?.pool_stats} />
            <EfficiencyPanel report={efficiency} onApplyConfig={applyConfig} />

            {chartSections.map(section => (
              <div className="admin-card admin-resources-chart-card" key={section.id}>
                {summaryCards(summary, section.field, section.label, section.tip)}
                <ResourceChartSection
                  series={series}
                  fields={section.fields}
                  labels={section.labels}
                  tableTitle={section.label}
                  hostProfile={payload?.host_profile}
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
