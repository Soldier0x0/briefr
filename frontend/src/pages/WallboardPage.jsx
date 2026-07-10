import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import useModalLayer from '../hooks/useModalLayer.js'
import {
  clearWallboardToken,
  createWallboardSession,
  fetchWallboard,
  getWallboardToken,
  setWallboardToken,
} from '../api.js'
import './WallboardPage.css'

const POLL_MS = 90_000
const TILE_ROTATE_MS = 12_000
const PAGE1_MS = 90_000
const PAGE2_MS = 45_000

function fmtRisk(score) {
  if (score === null || score === undefined) return '—'
  return Number(score).toFixed(1)
}

function fmtCount(value) {
  if (value === null || value === undefined) return '—'
  return String(value)
}

function openCve(cveId) {
  if (!cveId) return
  window.open(`/?cve=${encodeURIComponent(cveId)}`, '_blank', 'noopener,noreferrer')
}

function TokenModal({ onSubmit, error }) {
  const boxRef = useRef(null)
  const [value, setValue] = useState('')
  useModalLayer(true, boxRef, { trackDepth: true })

  return (
    <div className="wallboard-token-overlay" role="presentation">
      <div className="wallboard-token-dialog" ref={boxRef} role="dialog" aria-modal="true" aria-label="Wallboard token">
        <h2>Wallboard token required</h2>
        <p>Enter the read-only kiosk token configured on the server. A secure session cookie is set after connect.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            onSubmit(value.trim())
          }}
        >
          <input
            type="password"
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="WALLBOARD_TOKEN"
            className="wallboard-token-input"
          />
          {error && <p className="wallboard-token-error">{error}</p>}
          <button type="submit" className="wallboard-token-submit">Connect</button>
        </form>
      </div>
    </div>
  )
}

function TileShell({ label, active, children, className = '' }) {
  return (
    <article className={`wallboard-tile${active ? ' wallboard-tile--active' : ''} ${className}`.trim()}>
      <h2 className="wallboard-tile-label">{label}</h2>
      {children}
    </article>
  )
}

function CveLink({ cveId, children }) {
  return (
    <button type="button" className="wallboard-cve-link mono" onClick={() => openCve(cveId)}>
      {children || cveId}
    </button>
  )
}

function IngestStrip({ strip }) {
  if (!strip) return null
  const status = (strip.status || 'UNKNOWN').toLowerCase()
  return (
    <div className="wallboard-ingest-strip mono" aria-label="Ingest status">
      <span className={`wallboard-status-${status}`}>{strip.status}</span>
      <span>· CVEs {fmtCount(strip.cve_count)}</span>
      <span>· circuits {fmtCount(strip.open_circuits)}</span>
      {strip.nvd_age_hours != null && <span>· NVD {strip.nvd_age_hours}h</span>}
      {strip.kev_age_hours != null && <span>· KEV {strip.kev_age_hours}h</span>}
      {strip.epss_age_hours != null && <span>· EPSS {strip.epss_age_hours}h</span>}
    </div>
  )
}

function PageOne({ payload, activeTile }) {
  const stackTerms = payload?.meta?.stack_terms || []
  return (
    <div className="wallboard-page1">
      <div className="wallboard-hero-row">
        <TileShell label="KEV on stack" active={activeTile === 0}>
          <p className="wallboard-tile-metric mono">{fmtCount(payload?.kev_on_stack?.count)}</p>
          <p className="wallboard-tile-sub">
            {payload?.kev_on_stack?.stack_configured
              ? stackTerms.join(', ') || 'stack profile'
              : 'Configure stack in Feed'}
          </p>
        </TileShell>
        <TileShell label="KEV due <7d" active={activeTile === 1}>
          <p className="wallboard-tile-metric mono">{fmtCount(payload?.kev_due_soon?.count)}</p>
          <ul className="wallboard-mini-list">
            {(payload?.kev_due_soon?.items || []).slice(0, 3).map((item) => (
              <li key={item.cve_id}>
                <CveLink cveId={item.cve_id} />
                <span className="wallboard-tile-sub">{item.due_date}</span>
              </li>
            ))}
          </ul>
        </TileShell>
        <TileShell label="New KEV 24h" active={activeTile === 2}>
          <p className="wallboard-tile-metric mono">{fmtCount(payload?.changes_24h?.section_counts?.new_kev)}</p>
          <p className="wallboard-tile-sub mono">queue {fmtCount(payload?.changes_24h?.action_queue_count)}</p>
        </TileShell>
        <TileShell label="Top risk" active={activeTile === 3}>
          {payload?.top_risk?.items?.[0] ? (
            <>
              <p className="wallboard-tile-metric mono">{fmtRisk(payload.top_risk.items[0].risk_score)}</p>
              <CveLink cveId={payload.top_risk.items[0].cve_id} />
              <p className="wallboard-tile-sub">{payload.top_risk.items[0].summary}</p>
            </>
          ) : (
            <p className="wallboard-tile-metric mono">—</p>
          )}
        </TileShell>
      </div>

      <IngestStrip strip={payload?.ingest_strip} />

      <div className="wallboard-secondary-grid">
        <TileShell label="24h queue" active={activeTile === 4}>
          <ul className="wallboard-mini-list">
            {(payload?.changes_24h?.highlights || []).slice(0, 5).map((item) => (
              <li key={item.cve_id}>
                <CveLink cveId={item.cve_id} />
                {item.is_kev && <span className="wallboard-chip">KEV</span>}
              </li>
            ))}
          </ul>
        </TileShell>
        <TileShell label="EPSS movers" active={activeTile === 5}>
          <p className="wallboard-tile-metric mono">{fmtCount(payload?.epss_movers?.count)}</p>
          <ul className="wallboard-mini-list">
            {(payload?.epss_movers?.items || []).slice(0, 3).map((item) => (
              <li key={item.cve_id}>
                <CveLink cveId={item.cve_id} />
                <span>{item.epss_score != null ? Number(item.epss_score).toFixed(3) : '—'}</span>
              </li>
            ))}
          </ul>
        </TileShell>
        <TileShell label="Campaigns" active={activeTile === 6}>
          <p className="wallboard-tile-metric mono">{fmtCount(payload?.campaigns?.active_count)}</p>
          <ul className="wallboard-mini-list">
            {(payload?.campaigns?.items || []).slice(0, 3).map((item) => (
              <li key={item.campaign_id} className="mono">{item.name} ({item.member_count})</li>
            ))}
          </ul>
        </TileShell>
        <TileShell label="Coverage gaps" active={activeTile === 7}>
          <p className="wallboard-tile-metric mono">{fmtCount(payload?.coverage_gaps?.gap_count)}</p>
          <ul className="wallboard-mini-list">
            {(payload?.coverage_gaps?.top_gaps || []).slice(0, 3).map((gap) => (
              <li key={gap.technique_id}>
                <span className="mono">{gap.technique_id}</span>
                {gap.kev_count > 0 && <span className="wallboard-chip">KEV</span>}
              </li>
            ))}
          </ul>
        </TileShell>
      </div>
    </div>
  )
}

function PageTwo({ payload, activeTile }) {
  const rows = payload?.source_health?.rows || []
  return (
    <div className="wallboard-page2">
      <TileShell label="Source health" active={activeTile === 0} className="wallboard-tile--wide">
        <div className="wallboard-table-wrap">
          <table className="wallboard-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Circuit</th>
                <th>Last success</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={3}>No source data</td></tr>}
              {rows.map((row) => (
                <tr key={row.source}>
                  <td className="mono">{row.source}</td>
                  <td className={row.circuit_open ? 'wallboard-status-degraded' : 'wallboard-status-ok'}>
                    {row.circuit_open ? 'OPEN' : 'OK'}
                  </td>
                  <td className="mono">{row.last_success || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </TileShell>

      <div className="wallboard-secondary-grid">
        <TileShell label="24h queue (expanded)" active={activeTile === 1}>
          <ul className="wallboard-mini-list">
            {(payload?.changes_24h?.highlights || []).map((item) => (
              <li key={item.cve_id}>
                <CveLink cveId={item.cve_id} />
                <span className="wallboard-tile-sub">{item.summary}</span>
              </li>
            ))}
          </ul>
        </TileShell>
        <TileShell label="EPSS movers (full)" active={activeTile === 2}>
          <ul className="wallboard-mini-list">
            {(payload?.epss_movers?.items || []).map((item) => (
              <li key={item.cve_id}>
                <CveLink cveId={item.cve_id} />
                <span>{item.epss_score != null ? Number(item.epss_score).toFixed(3) : '—'}</span>
                <span className="wallboard-tile-sub">{item.summary}</span>
              </li>
            ))}
          </ul>
        </TileShell>
        <TileShell label="Active campaigns" active={activeTile === 3}>
          <ul className="wallboard-mini-list">
            {(payload?.campaigns?.items || []).map((item) => (
              <li key={item.campaign_id}>
                <span className="mono">{item.name}</span>
                <span className="wallboard-tile-sub">{item.member_count} CVEs · {item.confidence}</span>
              </li>
            ))}
          </ul>
        </TileShell>
      </div>
    </div>
  )
}

export default function WallboardPage() {
  const [searchParams] = useSearchParams()
  const [authenticated, setAuthenticated] = useState(false)
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState('')
  const [authError, setAuthError] = useState('')
  const [needsToken, setNeedsToken] = useState(false)
  const [activeTile, setActiveTile] = useState(0)
  const [page, setPage] = useState(1)
  const [manualPage, setManualPage] = useState(false)
  const [lastRefresh, setLastRefresh] = useState(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    const urlToken = searchParams.get('token')
    if (urlToken) {
      setWallboardToken(urlToken)
    }
  }, [searchParams])

  const load = useCallback(async () => {
    try {
      const data = await fetchWallboard()
      if (cancelledRef.current) return
      setPayload(data)
      setError('')
      setAuthError('')
      setNeedsToken(false)
      setAuthenticated(true)
      setLastRefresh(new Date())
    } catch (e) {
      if (cancelledRef.current) return
      if (e?.status === 401) {
        clearWallboardToken()
        setAuthenticated(false)
        setNeedsToken(true)
        setAuthError('Invalid or missing wallboard token')
        return
      }
      setError(e?.message || 'Failed to load wallboard')
    }
  }, [])

  useEffect(() => {
    cancelledRef.current = false
    load()
    const poll = setInterval(load, POLL_MS)
    return () => {
      cancelledRef.current = true
      clearInterval(poll)
    }
  }, [load])

  useEffect(() => {
    const rotate = setInterval(() => {
      setActiveTile((idx) => idx + 1)
    }, TILE_ROTATE_MS)
    return () => clearInterval(rotate)
  }, [])

  useEffect(() => {
    if (manualPage) return undefined
    const ms = page === 1 ? PAGE1_MS : PAGE2_MS
    const timer = setInterval(() => {
      setPage((p) => (p === 1 ? 2 : 1))
      setActiveTile(0)
    }, ms)
    return () => clearInterval(timer)
  }, [page, manualPage])

  const handleTokenSubmit = async (newToken) => {
    setAuthError('')
    try {
      await createWallboardSession(newToken)
      setWallboardToken(newToken)
      setAuthenticated(true)
      setNeedsToken(false)
      await load()
    } catch (e) {
      setAuthError(e?.message || 'Invalid wallboard token')
    }
  }

  const stackLabel = (payload?.meta?.stack_terms || []).join(', ') || 'no stack'

  return (
    <div className="wallboard-page">
      <header className="wallboard-header">
        <div className="wallboard-brand mono">BRIEFR</div>
        <div className="wallboard-header-stack mono">
          stack:
          {' '}
          {stackLabel}
        </div>
        <div className="wallboard-header-meta mono">
          {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString()}` : 'Loading…'}
          {payload?.meta?.generated_at && (
            <>
              {' '}
              ·
              {' '}
              {payload.meta.generated_at.replace('T', ' ').replace('Z', ' UTC')}
            </>
          )}
        </div>
        <div className="wallboard-page-controls mono">
          <button
            type="button"
            className={page === 1 ? 'wallboard-page-btn wallboard-page-btn--active' : 'wallboard-page-btn'}
            onClick={() => { setManualPage(true); setPage(1); setActiveTile(0) }}
          >
            Page 1
          </button>
          <button
            type="button"
            className={page === 2 ? 'wallboard-page-btn wallboard-page-btn--active' : 'wallboard-page-btn'}
            onClick={() => { setManualPage(true); setPage(2); setActiveTile(0) }}
          >
            Page 2
          </button>
          <button
            type="button"
            className="wallboard-page-btn"
            onClick={() => setManualPage(false)}
            title="Resume auto rotation"
          >
            Auto
          </button>
        </div>
      </header>

      {error && <div className="wallboard-banner wallboard-banner--error">{error}</div>}

      <section className="wallboard-body" aria-label="Intel posture tiles">
        {authenticated && page === 1 && (
          <PageOne payload={payload} activeTile={activeTile % 8} />
        )}
        {authenticated && page === 2 && (
          <PageTwo payload={payload} activeTile={activeTile % 4} />
        )}
      </section>

      <footer className="wallboard-ticker" aria-live="polite">
        <div className="wallboard-ticker-track">
          {((payload?.headlines?.items || []).length
            ? payload.headlines.items
            : [{ title: 'Incident feed warming…', source: 'BRIEFR' }]
          ).map((item, i) => (
            <span key={`${item.title}-${i}`} className="wallboard-ticker-item">
              <strong>{item.source ? `${item.source}: ` : ''}</strong>
              {item.title}
            </span>
          ))}
        </div>
      </footer>

      {needsToken && (
        <TokenModal onSubmit={handleTokenSubmit} error={authError} />
      )}
    </div>
  )
}
