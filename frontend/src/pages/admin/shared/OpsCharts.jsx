import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { adminApi } from '../../../api.js'
import { ChartDataTable } from '../../../components/ui/index.js'
import HelpTip from './HelpTip.jsx'
import { jobLabel } from '../catalog.js'
import { fmtBytes, fmtDur } from '../formatters.js'
import { AdminChartSkeleton } from './AdminSkeletons.jsx'

const IngestDurationChart = lazy(() =>
  import('./opsChartsRecharts.jsx').then((mod) => ({ default: mod.IngestDurationChart })),
)
const BackupSizesChart = lazy(() =>
  import('./opsChartsRecharts.jsx').then((mod) => ({ default: mod.BackupSizesChart })),
)
const WebhookDeliveriesChart = lazy(() =>
  import('./opsChartsRecharts.jsx').then((mod) => ({ default: mod.WebhookDeliveriesChart })),
)

const INGEST_JOB_IDS = [
  'nvd_incremental_sync',
  'kev_metadata_sync',
  'epss_score_sync',
  'sigmahq_index_sync',
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

function ChartSuspense({ children }) {
  return (
    <Suspense fallback={<AdminChartSkeleton height={200} />}>
      {children}
    </Suspense>
  )
}

export default function OpsCharts({ schedulerJobs }) {
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
            <ChartSuspense>
              <IngestDurationChart rows={ingestRows} />
            </ChartSuspense>
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
          <div className="admin-empty admin-ops-chart-empty">{extraLoaded ? 'No backups listed yet' : <AdminChartSkeleton height={160} />}</div>
        ) : (
          <>
            <ChartSuspense>
              <BackupSizesChart rows={backupRows} />
            </ChartSuspense>
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
          <div className="admin-empty admin-ops-chart-empty">{extraLoaded ? 'No webhook deliveries yet' : <AdminChartSkeleton height={160} />}</div>
        ) : (
          <>
            <ChartSuspense>
              <WebhookDeliveriesChart buckets={whBuckets} />
            </ChartSuspense>
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
