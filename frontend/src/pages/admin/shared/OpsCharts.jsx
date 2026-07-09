import { useEffect, useRef, useMemo, useState } from 'react'
import { adminApi } from '../../../api.js'
import { loadChartJs, readChartTheme } from '../../../utils/chartLoader.js'
import { prefersReducedMotion } from '../../../utils/motion.js'
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

function chartAnimationOptions() {
  return prefersReducedMotion() ? false : { duration: 160, easing: 'easeOutQuad' }
}

function baseOptions(theme) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: chartAnimationOptions(),
    layout: { padding: { left: 4, right: 8, top: 4, bottom: 4 } },
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
          maxRotation: 45,
          minRotation: 0,
        },
        grid: { color: theme.grid },
        border: { color: theme.grid },
      },
      y: {
        beginAtZero: true,
        ticks: {
          color: theme.textMuted,
          font: { family: theme.mono, size: 9 },
        },
        grid: { color: theme.grid },
        border: { color: theme.grid },
      },
    },
  }
}

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
      const shared = baseOptions(theme)

      chartsRef.current.ingest?.destroy()
      if (ingestRef.current && ingestRows.length) {
        chartsRef.current.ingest = new Chart(ingestRef.current, {
          type: 'bar',
          data: {
            labels: ingestRows.map(r => r.label),
            datasets: [{
              label: 'Last run (seconds)',
              data: ingestRows.map(r => r.seconds),
              backgroundColor: ingestRows.map(r => (
                r.hadError ? theme.redDim : theme.accent
              )),
              borderWidth: 0,
              borderRadius: 0,
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
                  label(ctx) {
                    const row = ingestRows[ctx.dataIndex]
                    const err = row?.hadError ? ' (last run errored)' : ''
                    return `${fmtDur(ctx.parsed.y)}${err}`
                  },
                },
              },
            },
          },
        })
      }

      chartsRef.current.backup?.destroy()
      if (backupRef.current && backupRows.length) {
        chartsRef.current.backup = new Chart(backupRef.current, {
          type: 'bar',
          data: {
            labels: backupRows.map(b => (b.filename || '').replace(/^briefr-backup-/, '').slice(0, 14)),
            datasets: [{
              label: 'Archive size',
              data: backupRows.map(b => b.size_bytes || 0),
              backgroundColor: theme.greenDim,
              borderColor: theme.green,
              borderWidth: 1,
              borderRadius: 0,
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
              x: { ...shared.scales.x, stacked: true },
              y: { ...shared.scales.y, stacked: true },
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
          <div className="admin-ops-chart-wrap"><canvas ref={ingestRef} /></div>
        )}
      </div>

      <div className="admin-card admin-ops-chart-card">
        <div className="admin-card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          Backup archive sizes
          <HelpTip text="Size of the eight most recent encrypted backup archives on disk (newest on the right)." />
        </div>
        {backupRows.length === 0 ? (
          <div className="admin-empty admin-ops-chart-empty">{extraLoaded ? 'No backups listed yet' : 'Loading…'}</div>
        ) : (
          <div className="admin-ops-chart-wrap"><canvas ref={backupRef} /></div>
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
          <div className="admin-ops-chart-wrap"><canvas ref={webhookRef} /></div>
        )}
      </div>
    </div>
  )
}
