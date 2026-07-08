import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import useModalLayer from '../hooks/useModalLayer.js'
import {
  clearWallboardToken,
  fetchWallboard,
  getWallboardToken,
  setWallboardToken,
} from '../api.js'
import './WallboardPage.css'

const POLL_MS = 90_000
const ROTATE_MS = 12_000
const TILE_KEYS = [
  'kev_on_stack',
  'changes_24h',
  'top_risk',
  'ingest_health',
  'coverage_gaps',
  'headlines',
]

function fmtRisk(score) {
  if (score === null || score === undefined) return '—'
  return Number(score).toFixed(1)
}

function fmtCount(value) {
  if (value === null || value === undefined) return '—'
  return String(value)
}

function healthStatus(ingest) {
  if (!ingest) return 'UNKNOWN'
  if (ingest.refresh_in_progress) return 'SYNCING'
  if ((ingest.open_circuit_count || 0) > 0) return 'DEGRADED'
  return 'OK'
}

function TokenModal({ onSubmit, error }) {
  const boxRef = useRef(null)
  const [value, setValue] = useState('')
  useModalLayer(true, boxRef, { trackDepth: true })

  return (
    <div className="wallboard-token-overlay" role="presentation">
      <div className="wallboard-token-dialog" ref={boxRef} role="dialog" aria-modal="true" aria-label="Wallboard token">
        <h2>Wallboard token required</h2>
        <p>Enter the read-only kiosk token configured on the server.</p>
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

function KevOnStackTile({ data, active }) {
  return (
    <article className={`wallboard-tile${active ? ' wallboard-tile--active' : ''}`}>
      <h2 className="wallboard-tile-label">KEV on stack</h2>
      <p className="wallboard-tile-metric mono">{fmtCount(data?.count)}</p>
      <p className="wallboard-tile-sub">
        {data?.stack_configured
          ? (data.stack_terms || []).join(', ') || 'stack profile'
          : 'Set stack in Feed (or BRIEFR_STACK_TERMS)'}
      </p>
    </article>
  )
}

function ChangesTile({ data, active }) {
  const counts = data?.section_counts || {}
  return (
    <article className={`wallboard-tile${active ? ' wallboard-tile--active' : ''}`}>
      <h2 className="wallboard-tile-label">New / changed 24h</h2>
      <p className="wallboard-tile-metric mono">{fmtCount(data?.action_queue_count)}</p>
      <ul className="wallboard-mini-list">
        {(data?.highlights || []).slice(0, 3).map((item) => (
          <li key={item.cve_id}>
            <span className="mono">{item.cve_id}</span>
            {item.is_kev && <span className="wallboard-chip">KEV</span>}
          </li>
        ))}
      </ul>
      <p className="wallboard-tile-sub mono">
        EPSS {counts.epss_movers || 0} · KEV {counts.new_kev || 0} · due {counts.kev_due_soon || 0}
      </p>
    </article>
  )
}

function TopRiskTile({ data, active }) {
  const top = (data?.items || [])[0]
  return (
    <article className={`wallboard-tile${active ? ' wallboard-tile--active' : ''}`}>
      <h2 className="wallboard-tile-label">Top risk CVEs</h2>
      {top ? (
        <>
          <p className="wallboard-tile-metric mono">{fmtRisk(top.risk_score)}</p>
          <p className="wallboard-tile-cve mono">{top.cve_id}</p>
          <p className="wallboard-tile-sub">{top.summary}</p>
        </>
      ) : (
        <p className="wallboard-tile-metric mono">—</p>
      )}
      <ul className="wallboard-mini-list">
        {(data?.items || []).slice(1, 4).map((item) => (
          <li key={item.cve_id} className="mono">
            {item.cve_id}
            {' '}
            {fmtRisk(item.risk_score)}
          </li>
        ))}
      </ul>
    </article>
  )
}

function IngestTile({ data, active }) {
  const status = healthStatus(data)
  return (
    <article className={`wallboard-tile${active ? ' wallboard-tile--active' : ''}`}>
      <h2 className="wallboard-tile-label">Ingest health</h2>
      <p className={`wallboard-tile-metric mono wallboard-status-${status.toLowerCase()}`}>{status}</p>
      <p className="wallboard-tile-sub mono">
        {fmtCount(data?.cve_count)}
        {' '}
        CVEs
      </p>
      <p className="wallboard-tile-sub">
        circuits open:
        {' '}
        {fmtCount(data?.open_circuit_count)}
        {' '}
        · incidents
        {' '}
        {data?.feeds?.incidents?.stale ? 'stale' : 'fresh'}
      </p>
    </article>
  )
}

function CoverageTile({ data, active }) {
  return (
    <article className={`wallboard-tile${active ? ' wallboard-tile--active' : ''}`}>
      <h2 className="wallboard-tile-label">Coverage gaps</h2>
      <p className="wallboard-tile-metric mono">{fmtCount(data?.gap_count)}</p>
      <p className="wallboard-tile-sub mono">
        yours {(data?.counts?.yours) ?? 0} · community {(data?.counts?.community) ?? 0}
      </p>
      <ul className="wallboard-mini-list">
        {(data?.top_gaps || []).slice(0, 3).map((gap) => (
          <li key={gap.technique_id}>
            <span className="mono">{gap.technique_id}</span>
            {gap.kev_count > 0 && <span className="wallboard-chip">KEV</span>}
          </li>
        ))}
      </ul>
    </article>
  )
}

function HeadlinesTile({ data, active }) {
  const first = (data?.items || [])[0]
  return (
    <article className={`wallboard-tile${active ? ' wallboard-tile--active' : ''}`}>
      <h2 className="wallboard-tile-label">Headline ticker</h2>
      <p className="wallboard-tile-headline">{first?.title || 'Waiting for incident snapshot…'}</p>
      <p className="wallboard-tile-sub">
        {first?.source || '—'}
        {data?.meta?.stale ? ' · stale feed' : ''}
      </p>
    </article>
  )
}

const TILE_COMPONENTS = {
  kev_on_stack: KevOnStackTile,
  changes_24h: ChangesTile,
  top_risk: TopRiskTile,
  ingest_health: IngestTile,
  coverage_gaps: CoverageTile,
  headlines: HeadlinesTile,
}

export default function WallboardPage() {
  const [searchParams] = useSearchParams()
  const [token, setToken] = useState(getWallboardToken)
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState('')
  const [authError, setAuthError] = useState('')
  const [needsToken, setNeedsToken] = useState(false)
  const [activeTile, setActiveTile] = useState(0)
  const [lastRefresh, setLastRefresh] = useState(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    const urlToken = searchParams.get('token')
    if (urlToken) {
      setWallboardToken(urlToken)
      setToken(urlToken)
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
      setLastRefresh(new Date())
    } catch (e) {
      if (cancelledRef.current) return
      if (e?.status === 401) {
        clearWallboardToken()
        setToken('')
        setNeedsToken(true)
        setAuthError('Invalid or missing wallboard token')
        return
      }
      setError(e?.message || 'Failed to load wallboard')
    }
  }, [])

  useEffect(() => {
    cancelledRef.current = false
    if (token) {
      load()
    } else {
      setNeedsToken(true)
    }
    const poll = setInterval(() => {
      if (token) load()
    }, POLL_MS)
    return () => {
      cancelledRef.current = true
      clearInterval(poll)
    }
  }, [load, token])

  useEffect(() => {
    const rotate = setInterval(() => {
      setActiveTile((idx) => (idx + 1) % TILE_KEYS.length)
    }, ROTATE_MS)
    return () => clearInterval(rotate)
  }, [])

  const handleTokenSubmit = (newToken) => {
    setWallboardToken(newToken)
    setToken(newToken)
    setAuthError('')
  }

  return (
    <div className="wallboard-page">
      <header className="wallboard-header">
        <div className="wallboard-brand">BRIEFR</div>
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
      </header>

      {error && <div className="wallboard-banner wallboard-banner--error">{error}</div>}

      <section className="wallboard-grid" aria-label="Intel posture tiles">
        {TILE_KEYS.map((key, index) => {
          const Tile = TILE_COMPONENTS[key]
          return (
            <Tile
              key={key}
              data={payload?.[key]}
              active={index === activeTile}
            />
          )
        })}
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
