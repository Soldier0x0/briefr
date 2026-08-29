import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Select } from '../../components/ui/index.js'
import { adminApi } from '../../api.js'
import HelpTip from './shared/HelpTip.jsx'
import { dailyBriefTestToast } from './toastCopy.js'
import './DailyBriefPage.css'

const SLOT_OPTIONS = [
  { value: 'eod', label: 'End of day' },
  { value: 'standup', label: 'Morning briefing' },
]

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
  }, [loadDestinations])

  const brief = preview?.brief
  const subscribed = useMemo(
    () =>
      (destinations || []).filter(
        (dest) => dest.enabled && Array.isArray(dest.event_types) && dest.event_types.includes('daily_brief'),
      ),
    [destinations],
  )
  const deliveryLabels = subscribed.map((dest) => dest.label || dest.id).filter(Boolean)

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
        <HelpTip text="Scheduled instance rollup for Discord, Telegram, and generic HTTPS. Real-time KEV and watchlist alerts stay on Webhooks." />
      </h1>
      <p className="admin-page-subtitle">
        Same facts as the channel report. Enable EOD / standup under Config, then subscribe destinations to Daily brief.
      </p>

      <div className="admin-card daily-brief-toolbar">
        <div className="admin-filter-bar admin-filter-bar--fields">
          <label className="admin-field">
            <span className="admin-field-label">Slot</span>
            <Select className="admin-select" value={slot} onChange={setSlot} options={SLOT_OPTIONS} />
          </label>
          <button type="button" className="admin-btn admin-btn-ghost" disabled={!!busy} onClick={previewBrief}>
            {busy === 'preview' ? 'Previewing…' : 'Preview'}
          </button>
          <button type="button" className="admin-btn admin-btn-primary" disabled={!!busy} onClick={sendTest}>
            {busy === 'test' ? 'Sending…' : 'Send test'}
          </button>
        </div>
        <p className="daily-brief-delivery">
          {destinationsLoading
            ? 'Loading destinations…'
            : destinationsError
              ? (
                <>
                  Could not load destinations.{' '}
                  <button type="button" className="admin-btn admin-btn-ghost" onClick={loadDestinations}>
                    Retry
                  </button>
                </>
              )
              : deliveryLabels.length
                ? `Sends to ${deliveryLabels.join(', ')} (Daily brief subscribed)`
                : 'No destinations subscribe to Daily brief yet.'}{' '}
          <Link to="/admin?p=webhooks">Configure events on Webhooks</Link>
        </p>
      </div>

      {error && (
        <p className="admin-page-subtitle" style={{ color: 'var(--red)' }} role="alert">
          {error}
        </p>
      )}

      {!brief && !error && (
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
