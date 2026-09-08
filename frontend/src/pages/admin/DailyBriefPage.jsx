import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Select } from '../../components/ui/index.js'
import { adminApi } from '../../api.js'
import HelpTip from './shared/HelpTip.jsx'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import { dailyBriefDeliveryCopy } from './dailyBriefCopy.js'
import { dailyBriefTestToast } from './toastCopy.js'
import './DailyBriefPage.css'

const SLOT_OPTIONS = [
  { value: 'eod', label: 'End of day' },
  { value: 'standup', label: 'Morning briefing' },
]

function flagOn(raw) {
  return raw === '1' || raw === 'true' || raw === true
}

function SectionCard({ title, children }) {
  if (children == null || children === false) return null
  return (
    <section className="daily-brief-section">
      <h2 className="daily-brief-section-title">{title}</h2>
      <div className="daily-brief-section-body">{children}</div>
    </section>
  )
}

function lineList(rows) {
  if (!rows?.length) return null
  return (
    <ul className="daily-brief-list">
      {rows.map((row) => (
        <li key={row}>{row}</li>
      ))}
    </ul>
  )
}

export default function DailyBriefPage({ toast }) {
  const [slot, setSlot] = useState('eod')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(null)
  const [destinations, setDestinations] = useState([])
  const [destinationsLoading, setDestinationsLoading] = useState(true)
  const [destinationsError, setDestinationsError] = useState(null)
  const [config, setConfig] = useState(null)
  const [configError, setConfigError] = useState(null)

  const loadDestinations = useCallback(async () => {
    setDestinationsLoading(true)
    setDestinationsError(null)
    try {
      const { data } = await adminApi.getJson('/webhooks/destinations')
      setDestinations(data?.destinations || [])
    } catch (e) {
      setDestinations([])
      setDestinationsError(e)
    } finally {
      setDestinationsLoading(false)
    }
  }, [])

  const loadConfig = useCallback(async () => {
    try {
      const { data } = await adminApi.getJson('/config')
      setConfig(data)
      setConfigError(null)
    } catch (e) {
      setConfigError(e)
    }
  }, [])

  async function saveSetting(key, value) {
    if (busy) return
    setBusy(key)
    setError(null)
    try {
      await adminApi.postJson('/config', { key, value: String(value) })
      await loadConfig()
      toast('Schedule saved', true)
    } catch (e) {
      toast(`Failed: ${e.message}`, false)
    } finally {
      setBusy(null)
    }
  }

  async function previewBrief() {
    setBusy('preview')
    setError(null)
    try {
      const { data } = await adminApi.getJson(
        `/webhooks/daily-brief/preview?slot=${encodeURIComponent(slot)}`,
      )
      setPreview(data)
      toast('Preview ready', true)
    } catch (e) {
      setError(e.message)
      toast(`Preview failed: ${e.message}`, false)
    } finally {
      setBusy(null)
    }
  }

  async function sendTest() {
    setBusy('test')
    setError(null)
    try {
      const { data } = await adminApi.postJson('/webhooks/daily-brief/test', { slot })
      if (data?.brief) setPreview(data)
      toast(dailyBriefTestToast(data))
    } catch (e) {
      setError(e.message)
      toast(`Test send failed: ${e.message}`, false)
    } finally {
      setBusy(null)
    }
  }

  useEffect(() => {
    loadDestinations()
    loadConfig()
  }, [loadDestinations, loadConfig])

  const brief = preview?.brief
  const subscribed = useMemo(
    () =>
      (destinations || []).filter(
        (dest) => dest.enabled && Array.isArray(dest.event_types) && dest.event_types.includes('daily_brief'),
      ),
    [destinations],
  )
  const deliveryLabels = subscribed.map((dest) => dest.label || dest.id).filter(Boolean)
  const delivery = dailyBriefDeliveryCopy({
    loading: destinationsLoading,
    error: destinationsError,
    labels: deliveryLabels,
  })
  const sched = config?.scheduler || {}
  const tz = sched.SCHEDULER_TIMEZONE || 'instance timezone'
  const scheduleLocked = Boolean(busy)

  const productLines = (brief?.market?.products || []).map(
    (p) =>
      `${p.label}  ${p.total}  (Critical ${p.critical} · High ${p.high} · Medium ${p.medium} · Low ${p.low})`,
  )
  const headlineLines = (brief?.headlines || []).map((row) => `${row.source} — ${row.title}`)
  const advisoryLines = (brief?.advisories || []).map((row) => `${row.source} — ${row.title}`)
  const opsLines = (brief?.ops || []).map((row) => `${row.id} — ${row.reason}`)

  return (
    <div>
      <h1 className="admin-page-title">
        Daily brief
        <HelpTip text="Scheduled instance rollup for Discord, Telegram, and generic HTTPS. Enable EOD and standup independently here. Preview / test slot does not change the schedule. Real-time KEV and watchlist alerts stay on Webhooks." />
      </h1>
      <p className="admin-page-subtitle">
        Enable EOD and/or morning standup on this page, then subscribe destinations to Daily brief on Webhooks. Real-time alerts are separate event types.
      </p>

      <div className="admin-card daily-brief-toolbar">
        {configError ? (
          <p className="daily-brief-error" role="alert">
            Could not load schedule flags.{' '}
            <button type="button" className="admin-btn admin-btn-ghost" onClick={loadConfig}>
              Retry
            </button>
          </p>
        ) : (
          <div className="daily-brief-schedule">
            <div className="daily-brief-slot-enable">
              <span className="admin-field-label">End of day</span>
              <ToggleSwitch
                on={flagOn(sched.DAILY_BRIEF_EOD_ENABLED)}
                disabled={scheduleLocked || !config}
                onChange={(next) => saveSetting('DAILY_BRIEF_EOD_ENABLED', next ? '1' : '0')}
                aria-label="Enable end of day brief"
              />
              <label className="admin-field daily-brief-time">
                <span className="admin-field-label">Hour</span>
                <input
                  className="admin-input"
                  type="number"
                  min={0}
                  max={23}
                  disabled={scheduleLocked || !config}
                  defaultValue={sched.DAILY_BRIEF_EOD_HOUR ?? 18}
                  key={`eod-h-${sched.DAILY_BRIEF_EOD_HOUR}`}
                  onBlur={(e) => saveSetting('DAILY_BRIEF_EOD_HOUR', e.target.value)}
                />
              </label>
              <label className="admin-field daily-brief-time">
                <span className="admin-field-label">Minute</span>
                <input
                  className="admin-input"
                  type="number"
                  min={0}
                  max={59}
                  disabled={scheduleLocked || !config}
                  defaultValue={sched.DAILY_BRIEF_EOD_MINUTE ?? 0}
                  key={`eod-m-${sched.DAILY_BRIEF_EOD_MINUTE}`}
                  onBlur={(e) => saveSetting('DAILY_BRIEF_EOD_MINUTE', e.target.value)}
                />
              </label>
            </div>
            <div className="daily-brief-slot-enable">
              <span className="admin-field-label">Morning briefing</span>
              <ToggleSwitch
                on={flagOn(sched.DAILY_BRIEF_STANDUP_ENABLED)}
                disabled={scheduleLocked || !config}
                onChange={(next) => saveSetting('DAILY_BRIEF_STANDUP_ENABLED', next ? '1' : '0')}
                aria-label="Enable morning briefing"
              />
              <label className="admin-field daily-brief-time">
                <span className="admin-field-label">Hour</span>
                <input
                  className="admin-input"
                  type="number"
                  min={0}
                  max={23}
                  disabled={scheduleLocked || !config}
                  defaultValue={sched.DAILY_BRIEF_STANDUP_HOUR ?? 7}
                  key={`stand-h-${sched.DAILY_BRIEF_STANDUP_HOUR}`}
                  onBlur={(e) => saveSetting('DAILY_BRIEF_STANDUP_HOUR', e.target.value)}
                />
              </label>
              <label className="admin-field daily-brief-time">
                <span className="admin-field-label">Minute</span>
                <input
                  className="admin-input"
                  type="number"
                  min={0}
                  max={59}
                  disabled={scheduleLocked || !config}
                  defaultValue={sched.DAILY_BRIEF_STANDUP_MINUTE ?? 0}
                  key={`stand-m-${sched.DAILY_BRIEF_STANDUP_MINUTE}`}
                  onBlur={(e) => saveSetting('DAILY_BRIEF_STANDUP_MINUTE', e.target.value)}
                />
              </label>
            </div>
            <p className="daily-brief-muted">Times are {tz}. Both slots may be on. Preview / test does not enable a slot.</p>
          </div>
        )}
        <div className="admin-filter-bar admin-filter-bar--fields">
          <label className="admin-field">
            <span className="admin-field-label">Preview / test slot</span>
            <Select className="admin-select" value={slot} onChange={setSlot} options={SLOT_OPTIONS} />
          </label>
          <button type="button" className="admin-btn admin-btn-ghost" disabled={!!busy} onClick={previewBrief}>
            {busy === 'preview' ? 'Previewing…' : 'Preview'}
          </button>
          <button type="button" className="admin-btn admin-btn-primary" disabled={!!busy} onClick={sendTest}>
            {busy === 'test' ? 'Sending…' : 'Send test'}
          </button>
        </div>
        <p
          className={delivery.kind === 'empty' ? 'daily-brief-error' : 'daily-brief-delivery'}
          role={delivery.kind === 'empty' || delivery.kind === 'error' ? 'alert' : undefined}
        >
          {delivery.kind === 'error' ? (
            <>
              {delivery.text}{' '}
              <button type="button" className="admin-btn admin-btn-ghost" onClick={loadDestinations}>
                Retry
              </button>
            </>
          ) : (
            delivery.text
          )}{' '}
          <Link to="/admin?p=webhooks">Configure events on Webhooks</Link>
        </p>
      </div>

      {error && (
        <p className="daily-brief-error" role="alert">
          {error}
        </p>
      )}

      {busy === 'preview' && !brief && (
        <p className="admin-page-subtitle" role="status">
          Loading preview…
        </p>
      )}

      {!brief && !error && busy !== 'preview' && (
        <p className="admin-page-subtitle" role="status">
          Preview a slot to load the current window.
        </p>
      )}

      {brief && (
        <div className="daily-brief-grid">
          <SectionCard title="Summary">
            <p>{brief.headline || 'Quiet window.'}</p>
          </SectionCard>
          <SectionCard title="At a glance">
            {lineList([
              `New on CISA KEV: ${brief.counts?.kev_new ?? 0}`,
              `Matches My Stack: ${brief.counts?.stack_matches ?? 0}`,
              `Pinned-CVE alerts: ${brief.counts?.watchlist ?? 0}`,
              `IOC watch hits: ${brief.counts?.ioc_hits ?? 0}`,
              `New Critical or High: ${brief.counts?.critical_high_new ?? 0}`,
              `Instance problems: ${brief.counts?.ops_issues ?? 0}`,
            ])}
          </SectionCard>
          {brief.market?.published > 0 && (
            <SectionCard title="Coverage">
              <p>
                Named products {(brief.market.published || 0) - (brief.market.unmapped || 0)} of {brief.market.published} · Unmapped {brief.market.unmapped || 0}
              </p>
              <p className="daily-brief-muted">
                Unmapped means NVD has not given these CVEs a product (CPE) yet. This briefing is a snapshot.
              </p>
            </SectionCard>
          )}
          {productLines.length > 0 && <SectionCard title="Published by product">{lineList(productLines)}</SectionCard>}
          {headlineLines.length > 0 && <SectionCard title="Headlines">{lineList(headlineLines)}</SectionCard>}
          {advisoryLines.length > 0 && <SectionCard title="Advisories">{lineList(advisoryLines)}</SectionCard>}
          {opsLines.length > 0 && <SectionCard title="Instance problems">{lineList(opsLines)}</SectionCard>}
          <details className="daily-brief-channel">
            <summary>Channel preview</summary>
            <pre>{JSON.stringify(preview?.discord_embeds || preview?.html || preview?.text, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  )
}
