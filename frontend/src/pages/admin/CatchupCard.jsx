import { useCallback, useEffect, useMemo, useState } from 'react'

import { adminApi, getAdminRequestId } from '../../api.js'
import { DateTimePicker } from '../../components/ui/index.js'
import { AdminFormSkeleton } from './shared/AdminSkeletons.jsx'
import {
  CATCHUP_DESCRIPTION,
  durationPresets,
  formatCatchupEndsIn,
} from './catchupCopy.js'

function formatLocal(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function formatUtc(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toISOString().replace('T', ' ').replace('Z', ' UTC')
  } catch {
    return iso
  }
}

async function readError(res, fallback) {
  const requestId = getAdminRequestId(res)
  const data = await res.json().catch(() => ({}))
  const detail = data?.detail
  const message = typeof detail === 'string'
    ? detail
    : Array.isArray(detail)
      ? detail.map((item) => item.msg || String(item)).join('; ')
      : fallback
  return { message, requestId }
}

function apiQueueSummary(queue) {
  if (!queue) return null
  return [
    `${queue.total_queued ?? 0} queued`,
    `${queue.total_active ?? 0} active`,
    queue.has_pending ? 'pending work' : 'no pending work',
  ].join(' · ')
}

export default function CatchupCard({ toast }) {
  const defaultPreset = useMemo(
    () => durationPresets.find((preset) => preset.default) || durationPresets[0],
    [],
  )
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedHours, setSelectedHours] = useState(defaultPreset.hours)
  const [customEnd, setCustomEnd] = useState('')
  const [busy, setBusy] = useState(false)

  const loadCatchup = useCallback(async ({ suppressLoading = false } = {}) => {
    if (!suppressLoading) setLoading(true)
    try {
      const res = await adminApi.get('/catchup')
      if (!res.ok) throw await readError(res, `HTTP ${res.status}`)
      setStatus(await res.json())
      setError(null)
    } catch (err) {
      setError({
        message: err?.message || 'Failed to load Catch-up mode',
        requestId: err?.requestId || null,
      })
    } finally {
      if (!suppressLoading) setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadCatchup()
  }, [loadCatchup])

  useEffect(() => {
    if (!status?.active) return undefined
    const id = setInterval(() => loadCatchup({ suppressLoading: true }), 15000)
    return () => clearInterval(id)
  }, [loadCatchup, status?.active])

  async function startCatchup() {
    setBusy(true)
    setError(null)
    try {
      const body = customEnd
        ? { ends_at: new Date(customEnd).toISOString() }
        : { duration_hours: selectedHours }
      const res = await adminApi.post('/catchup/start', body)
      if (!res.ok) throw await readError(res, `HTTP ${res.status}`)
      setStatus(await res.json())
      toast?.('Catch-up started', true)
      await loadCatchup({ suppressLoading: true })
    } catch (err) {
      setError({
        message: err?.message || 'Failed to start Catch-up mode',
        requestId: err?.requestId || null,
      })
      toast?.(err?.message || 'Failed to start Catch-up mode', false)
    } finally {
      setBusy(false)
    }
  }

  async function stopCatchup() {
    setBusy(true)
    setError(null)
    try {
      const res = await adminApi.post('/catchup/stop', {})
      if (!res.ok) throw await readError(res, `HTTP ${res.status}`)
      setStatus(await res.json())
      toast?.('Catch-up ended', true)
      await loadCatchup({ suppressLoading: true })
    } catch (err) {
      setError({
        message: err?.message || 'Failed to end Catch-up mode',
        requestId: err?.requestId || null,
      })
      toast?.(err?.message || 'Failed to end Catch-up mode', false)
    } finally {
      setBusy(false)
    }
  }

  function selectPreset(hours) {
    setSelectedHours(hours)
    setCustomEnd('')
  }

  const queueSummary = apiQueueSummary(status?.api_queue)
  const endsIn = formatCatchupEndsIn(status?.ends_at)

  return (
    <div className="admin-card">
      <div className="admin-card-title">Catch-up mode</div>

      {loading && !status ? (
        <AdminFormSkeleton fields={3} />
      ) : error && !status ? (
        <div className="admin-callout admin-callout-red" role="alert">
          <span>
            {error.message}
            {error.requestId ? (
              <>
                {' '}
                <span className="mono">ref: {error.requestId}</span>
              </>
            ) : null}
          </span>
          <button type="button" className="admin-btn admin-btn-ghost" onClick={() => loadCatchup()}>
            Retry
          </button>
        </div>
      ) : status?.active ? (
        <>
          <p className="admin-page-subtitle">{CATCHUP_DESCRIPTION}</p>
          {status.in_wind_down ? (
            <div className="admin-callout admin-callout-amber" role="status">
              Catch-up is winding down; new Catch-up ticks will not start before the end time.
            </div>
          ) : null}
          <table className="admin-table">
            <tbody>
              <tr>
                <th scope="row">Ends</th>
                <td>{formatLocal(status.ends_at)}</td>
              </tr>
              <tr>
                <th scope="row">Ends UTC</th>
                <td className="mono">{formatUtc(status.ends_at)}</td>
              </tr>
              <tr>
                <th scope="row">Remaining</th>
                <td>{endsIn}</td>
              </tr>
              <tr>
                <th scope="row">Started by</th>
                <td>{status.started_by || 'operator'}</td>
              </tr>
              {queueSummary ? (
                <tr>
                  <th scope="row">API queue</th>
                  <td>{queueSummary}</td>
                </tr>
              ) : null}
            </tbody>
          </table>
          <div className="admin-action-bar">
            <button type="button" className="admin-btn admin-btn-ghost" onClick={stopCatchup} disabled={busy}>
              {busy ? 'Ending…' : 'End early'}
            </button>
          </div>
          {error ? (
            <div className="admin-callout admin-callout-red" role="alert">
              {error.message}
              {error.requestId ? (
                <>
                  {' '}
                  <span className="mono">ref: {error.requestId}</span>
                </>
              ) : null}
            </div>
          ) : null}
        </>
      ) : (
        <>
          <p className="admin-page-subtitle">{CATCHUP_DESCRIPTION}</p>
          <div className="admin-filter-bar admin-filter-bar--fields">
            <div className="admin-field" role="group" aria-label="Catch-up duration">
              <span className="admin-field-label">Duration</span>
              <div className="admin-action-bar">
                {durationPresets.map((preset) => (
                  <button
                    key={preset.hours}
                    type="button"
                    className={`filter-chip ${selectedHours === preset.hours && !customEnd ? 'active' : ''}`}
                    aria-pressed={selectedHours === preset.hours && !customEnd}
                    onClick={() => selectPreset(preset.hours)}
                  >
                    {preset.hours}h
                  </button>
                ))}
              </div>
            </div>
            <div className="admin-field">
              <span className="admin-field-label">Custom end</span>
              <DateTimePicker
                value={customEnd}
                onChange={(value) => {
                  setCustomEnd(value)
                  setSelectedHours(value ? null : defaultPreset.hours)
                }}
                ariaLabel="Select custom Catch-up end time"
              />
            </div>
            <button type="button" className="admin-btn admin-btn-primary" onClick={startCatchup} disabled={busy}>
              {busy ? 'Starting…' : 'Start Catch-up'}
            </button>
          </div>
          {status?.cleared_reason ? (
            <div className="admin-empty admin-empty--compact">
              Last Catch-up ended: {status.cleared_reason.replace(/_/g, ' ')}
            </div>
          ) : null}
          {error ? (
            <div className="admin-callout admin-callout-red" role="alert">
              {error.message}
              {error.requestId ? (
                <>
                  {' '}
                  <span className="mono">ref: {error.requestId}</span>
                </>
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}
