import { useEffect, useRef, useMemo, useState } from 'react'
import { adminApi } from '../../../api.js'
import { loadChartJs, readChartTheme } from '../../../utils/chartLoader.js'
import { axisTitle, baseChartOptions } from '../../../utils/chartOptions.js'
import { ChartDataTable } from '../../../components/ui/index.js'
import HelpTip from './HelpTip.jsx'
import { jobLabel } from '../catalog.js'
import { fmtBytes, fmtDur } from '../formatters.js'

const INGEST_JOB_IDS = [
  'nvd_incremental_sync',
  'kev_metadata_sync',
  'epss_score_sync',
  'cvelistv5_incremental_sync',
  'otx_nightly_correlation',
  'exploit_sources_sync',
  'vulnrichment_snapshot_sync',
]

function ingestDurationRows(schedulerJobs) {
  const byId = new Map((schedulerJobs || []).map(j => [j.id, j]))
  return INGEST_JOB_IDS
    .map(id => {
      const job = byId.get(id)
      const sec = job?.last_run_duration_seconds
      if (sec == null || sec <= 0) return null
      return {
        id,
        label: jobLabel(id, 'operator'),
        seconds: sec,
        hadError: job?.last_run_had_error,
      }
    })
    .filter(Boolean)
    .sort((a, b) => b.seconds - a.seconds)
    .slice(0, 8)
}

function backupSizeRows(backups) {
  const rows = Array.isArray(backups) ? backups : []
  return [...rows]
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
    .slice(0, 8)
    .reverse()
}

function backupSparklineLabel(row) {
  const name = (row?.filename || '').replace(/^briefr-backup-/, '').replace(/\.tar\.gz$/, '')
  if (!name) return 'backup'
  return name.length > 12 ? `${name.slice(0, 12)}…` : name
}

function webhookDayBuckets(rows) {
  const buckets = new Map()
  for (const row of rows || []) {
    const day = (row.attempted_at || '').slice(0, 10)
    if (!day) continue
    const cur = buckets.get(day) || { ok: 0, failed: 0 }
    if (row.status === 'ok') cur.ok += 1
    else cur.failed += 1
    buckets.set(day, cur)
  }
  const days = [...buckets.keys()].sort().slice(-7)
  return days.map(day => ({
    day,
    ok: buckets.get(day)?.ok || 0,
    failed: buckets.get(day)?.failed || 0,
  }))
}

function ingestScaleMax(secondsList) {
  if (!secondsList.length) return undefined
  const sorted = [...secondsList].sort((a, b) => a - b)
  const p75 = sorted[Math.floor(sorted.length * 0.75)] || sorted[sorted.length - 1]
  const cap = Math.max(p75 * 1.25, sorted[0])
  return cap > 0 ? cap : undefined
}

export default function OpsCharts({ schedulerJobs }) {
  const ingestRef = useRef(null)
  const backupRef = useRef(null)
  const webhookRef = useRef(null)
  const chartsRef = useRef({})
  const [backups, setBackups] = useState([])
  const [webhookRows, setWebhookRows] = useState([])
  const [extraLoaded, setExtraLoaded] = useState(false)

  const ingestRows = useMemo(() => ingestDurationRows(schedulerJobs), [schedulerJobs])
  const backupRows = useMemo(() => backupSizeRows(backups), [backups])
  const whBuckets = useMemo(() => webhookDayBuckets(webhookRows), [webhookRows])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [backRes, whRes] = await Promise.all([
          adminApi.get('/backups'),
          adminApi.get('/webhooks/delivery-log?limit=200'),
        ])
        if (cancelled) return
        setBackups(backRes.ok ? await backRes.json() : [])
        const whPayload = whRes.ok ? await whRes.json() : { rows: [] }
        setWebhookRows(whPayload.rows || [])
      } catch {
        if (!cancelled) {
          setBackups([])
          setWebhookRows([])
        }
      } finally {
        if (!cancelled) setExtraLoaded(true)
      }
    })()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function render() {
      const Chart = await loadChartJs()
      if (cancelled) return
      const theme = readChartTheme()
      const shared = baseChartOptions(theme)

      chartsRef.current.ingest?.destroy()
      if (ingestRef.current && ingestRows.length) {
        const durations = ingestRows.map(r => r.seconds)
        const scaleMax = ingestScaleMax(durations)
        chartsRef.current.ingest = new Chart(ingestRef.current, {
          type: 'bar',
          data: {
            labels: ingestRows.map(r => r.label),
            datasets: [{
              label: 'Last run duration',
              data: durations,
              backgroundColor: ingestRows.map(r => (
                r.hadError ? theme.redDim : theme.accent
              )),
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
                    const row = ingestRows[ctx[0]?.dataIndex]
                    return row?.label || ctx[0]?.label || ''
                  },
                  label(ctx) {
                    const row = ingestRows[ctx.dataIndex]
                    const err = row?.hadError ? ' (last run errored)' : ''
                    return `${fmtDur(ctx.parsed.x)}${err}`
                  },
                },
              },
            },
            scales: {
              x: {
                ...shared.scales.x,
                suggestedMax: scaleMax,
                ticks: {
                  ...shared.scales.x.ticks,
                  callback: (v) => fmtDur(Number(v)),
                },
                title: axisTitle(theme, 'Duration'),
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

      chartsRef.current.backup?.destroy()
      if (backupRef.current && backupRows.length) {
        chartsRef.current.backup = new Chart(backupRef.current, {
          type: 'line',
          data: {
            labels: backupRows.map(backupSparklineLabel),
            datasets: [{
              label: 'Archive size',
              data: backupRows.map(b => b.size_bytes || 0),
              borderColor: theme.green,
              backgroundColor: theme.greenDim,
              fill: true,
              tension: 0.25,
              pointRadius: 3,
              pointHoverRadius: 4,
              borderWidth: 2,
            }],
          },
          options: {
            ...shared,
            plugins: {
              ...shared.plugins,
              legend: { display: false },
              tooltip: {
                ...shared.plugins.tooltip,
                callbacks: {
                  title(ctx) {
                    const row = backupRows[ctx[0]?.dataIndex]
                    return row?.filename || ctx[0]?.label || ''
                  },
                  label(ctx) {
                    return fmtBytes(ctx.parsed.y)
                  },
                  afterLabel(ctx) {
                    const row = backupRows[ctx.dataIndex]
                    return row?.created_at ? String(row.created_at).slice(0, 19) : ''
                  },
                },
              },
            },
            scales: {
              x: {
                ...shared.scales.x,
                ticks: {
                  ...shared.scales.x.ticks,
                  maxRotation: 0,
                },
                title: axisTitle(theme, 'Newest →'),
              },
              y: {
                ...shared.scales.y,
                ticks: {
                  ...shared.scales.y.ticks,
                  callback: (v) => fmtBytes(Number(v)),
                },
                title: axisTitle(theme, 'Size'),
              },
            },
          },
        })
      }

      chartsRef.current.webhook?.destroy()
      if (webhookRef.current && whBuckets.length) {
        chartsRef.current.webhook = new Chart(webhookRef.current, {
          type: 'bar',
          data: {
            labels: whBuckets.map(b => b.day.slice(5)),
            datasets: [
              {
                label: 'Delivered',
                data: whBuckets.map(b => b.ok),
                backgroundColor: theme.greenDim,
                borderWidth: 0,
                borderRadius: 0,
              },
              {
                label: 'Failed',
                data: whBuckets.map(b => b.failed),
                backgroundColor: theme.redDim,
                borderWidth: 0,
                borderRadius: 0,
              },
            ],
          },
          options: {
            ...shared,
            plugins: {
              ...shared.plugins,
              legend: {
                ...shared.plugins.legend,
                position: 'bottom',
              },
            },
            scales: {
              ...shared.scales,
              x: {
                ...shared.scales.x,
                stacked: true,
                title: axisTitle(theme, 'Day (UTC)'),
              },
              y: {
                ...shared.scales.y,
                stacked: true,
                ticks: {
                  ...shared.scales.y.ticks,
                  precision: 0,
                },
                title: axisTitle(theme, 'Deliveries'),
              },
            },
          },
        })
      }
    }

    const timer = setTimeout(() => { render() }, 300)
    return () => {
      cancelled = true
      clearTimeout(timer)
      Object.values(chartsRef.current).forEach(c => c?.destroy())
      chartsRef.current = {}
    }
  }, [ingestRows, backupRows, whBuckets, extraLoaded])

  return (
    <div className="admin-ops-charts">
      <div className="admin-card admin-ops-chart-card">
        <div className="admin-card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          Ingest duration (last run)
          <HelpTip text="Seconds the most recent scheduler run took for each core ingest job. Spikes often mean upstream slowness or a large delta batch." />
        </div>
        {ingestRows.length === 0 ? (
          <div className="admin-empty admin-ops-chart-empty">No ingest runs recorded yet</div>
        ) : (
          <>
            <div className="admin-ops-chart-wrap">
              <canvas ref={ingestRef} role="img" aria-label="Ingest job duration chart" />
            </div>
            <ChartDataTable
              title="Ingest job duration (last run)"
              columns={[
                { key: 'label', label: 'Job' },
                { key: 'duration', label: 'Duration', className: 'mono' },
                {
                  key: 'status',
                  label: 'Status',
                  className: 'mono',
                  render: (row) => (row.hadError ? 'Error' : 'OK'),
                },
              ]}
              rows={ingestRows.map((row) => ({
                _key: row.id,
                label: row.label,
                duration: fmtDur(row.seconds),
                hadError: row.hadError,
              }))}
            />
          </>
        )}
      </div>

      <div className="admin-card admin-ops-chart-card">
        <div className="admin-card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          Backup archive sizes
          <HelpTip text="Trend of the eight most recent encrypted backup archives on disk (oldest left, newest right)." />
        </div>
        {backupRows.length === 0 ? (
          <div className="admin-empty admin-ops-chart-empty">{extraLoaded ? 'No backups listed yet' : 'Loading…'}</div>
        ) : (
          <>
            <div className="admin-ops-chart-wrap">
              <canvas ref={backupRef} role="img" aria-label="Backup archive sizes chart" />
            </div>
            <ChartDataTable
              title="Backup archive sizes"
              columns={[
                { key: 'filename', label: 'Archive' },
                { key: 'size', label: 'Size', className: 'mono' },
                { key: 'created_at', label: 'Created (UTC)', className: 'mono' },
              ]}
              rows={backupRows.map((row) => ({
                _key: row.filename,
                filename: row.filename,
                size: fmtBytes(row.size_bytes || 0),
                created_at: row.created_at ? String(row.created_at).slice(0, 19) : '—',
              }))}
            />
          </>
        )}
      </div>

      <div className="admin-card admin-ops-chart-card">
        <div className="admin-card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          Webhook deliveries (7d)
          <HelpTip text="Daily count of successful vs failed webhook delivery attempts from the delivery log (last 200 rows)." />
        </div>
        {whBuckets.length === 0 ? (
          <div className="admin-empty admin-ops-chart-empty">{extraLoaded ? 'No webhook deliveries yet' : 'Loading…'}</div>
        ) : (
          <>
            <div className="admin-ops-chart-wrap">
              <canvas ref={webhookRef} role="img" aria-label="Webhook deliveries chart" />
            </div>
            <ChartDataTable
              title="Webhook deliveries (7d)"
              columns={[
                { key: 'day', label: 'Day (UTC)', className: 'mono' },
                { key: 'ok', label: 'Delivered', className: 'mono' },
                { key: 'failed', label: 'Failed', className: 'mono' },
              ]}
              rows={whBuckets.map((row) => ({
                _key: row.day,
                day: row.day,
                ok: row.ok,
                failed: row.failed,
              }))}
            />
          </>
        )}
      </div>
    </div>
  )
}
