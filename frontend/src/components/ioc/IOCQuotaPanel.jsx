import { useState, useEffect, useCallback } from 'react'
import { fetchIOCUsage } from '../../api.js'
import { ingestLogUrl } from '../../utils/adminLinks.js'

function quotaBarColor(warning) {
  if (!warning) return 'var(--text2)'
  if (warning.includes('exceeded')) return 'var(--red)'
  if (warning.includes('near')) return 'var(--amber)'
  return 'var(--text2)'
}

function UsageMeter({ label, used, limit, percentUsed, warning }) {
  if (limit == null) {
    return (
      <div className="quota-meter quota-meter--unmetered">
        <div className="quota-meter-head">
          <span className="quota-meter-label">{label}</span>
          <span className="quota-meter-val mono">{used.toLocaleString()} today</span>
        </div>
        <p className="quota-meter-note mono">// no published daily cap · fair use</p>
      </div>
    )
  }

  const pct = Math.min(Math.max(percentUsed ?? 0, 0), 100)
  const fillColor = quotaBarColor(warning)

  return (
    <div className="quota-meter">
      <div className="quota-meter-head">
        <span className="quota-meter-label">{label}</span>
        <span className="quota-meter-val mono" style={{ color: fillColor }}>
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div
        className="quota-track"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${Math.round(pct)}% of daily quota used`}
      >
        <div
          className="quota-fill"
          style={{ width: `${pct}%`, background: fillColor }}
        />
      </div>
    </div>
  )
}

function quotaChipFillClass(warning) {
  if (!warning) return ''
  if (warning.includes('exceeded')) return 'danger'
  if (warning.includes('near')) return 'warn'
  return ''
}

function serviceDisplayName(svc) {
  if (svc.service === 'greynoise') return 'GreyNoise'
  return svc.name
}

function quotaChipSummary(svc) {
  if (svc.this_week?.limit != null) {
    const u = svc.this_week.used ?? 0
    const l = svc.this_week.limit
    return `${u} / ${l} week`
  }
  if (svc.today?.limit != null) {
    const u = svc.today.used ?? 0
    const l = svc.today.limit
    return `${u} / ${l} today`
  }
  return `${svc.today?.used ?? 0} calls`
}

function quotaChipPercent(svc) {
  if (svc.this_week?.limit != null) return svc.this_week.percent_used ?? 0
  if (svc.today?.limit != null) return svc.today.percent_used ?? 0
  return null
}

export default function IOCQuotaPanel() {
  const [detailOpen, setDetailOpen] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)

  const loadUsage = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    fetchIOCUsage()
      .then(payload => {
        if (!cancelled) setData(payload)
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Could not load quota')
          setErrorRequestId(err?.requestId || null)
          setData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => loadUsage(), [loadUsage])

  const services = data?.services || []

  return (
    <div className="ioc-quota-wrap" role="region" aria-label="IOC API quota usage">
      <div className="ioc-quota-panel" id="ioc-quota-panel">
        <p className="ioc-quota-asof mono" style={{ marginBottom: 10 }}>
          // API QUOTA — BRIEFR calls from this server
          {!loading && data?.today_date_utc && (
            <> · UTC {data.today_date_utc}{data.as_of_utc ? ` ${data.as_of_utc.slice(11, 19)}` : ''}</>
          )}
        </p>

        {loading && (
          <p className="ioc-quota-loading mono">// Loading usage counters…</p>
        )}
        {error && (
          <p className="ioc-quota-error mono" role="alert">
            {error}
            {errorRequestId && (
              <>
                {' '}
                (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                  ref: {errorRequestId}
                </a>)
              </>
            )}
            {' '}
            <button type="button" className="ioc-quota-retry-btn" onClick={loadUsage}>
              Retry
            </button>
          </p>
        )}

        {!loading && !error && services.length > 0 && (
          <div className="ioc-quota-strip">
            {services.map(svc => {
              const pct = quotaChipPercent(svc)
              return (
                <div key={svc.service} className="ioc-quota-chip">
                  <span className="ioc-quota-chip-name mono">{serviceDisplayName(svc)}</span>
                  <span className="ioc-quota-chip-val mono">{quotaChipSummary(svc)}</span>
                  <div className="ioc-quota-chip-bar" aria-hidden={pct == null}>
                    {pct != null && (
                      <div
                        className={`ioc-quota-chip-fill ${quotaChipFillClass(svc.warning)}`}
                        style={{ width: `${Math.min(pct, 100)}%` }}
                      />
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <button
          type="button"
          className="ioc-quota-toggle mono"
          onClick={() => setDetailOpen(o => !o)}
          aria-expanded={detailOpen}
        >
          <span className={`ioc-quota-chevron${detailOpen ? '' : ' collapsed'}`} aria-hidden="true">▾</span>
          {detailOpen ? 'Hide limits & notes' : 'Show limits & notes'}
        </button>

        {detailOpen && !loading && !error && services.length > 0 && (
          <div className="ioc-quota-detail" style={{ marginTop: 12 }}>
            {services.map(svc => (
              <div key={svc.service} className="quota-service-block">
                <div className="quota-service-title">
                  <span className="mono">{serviceDisplayName(svc)}</span>
                  {svc.rate_limit && (
                    <span className="quota-rate mono">{svc.rate_limit}</span>
                  )}
                </div>
                {svc.today?.limit != null && (
                  <UsageMeter
                    label="Today"
                    used={svc.today?.used ?? 0}
                    limit={svc.today?.limit}
                    percentUsed={svc.today?.percent_used}
                    warning={svc.warning}
                  />
                )}
                {svc.this_week?.limit != null && (
                  <UsageMeter
                    label="This week (UTC Mon–Sun)"
                    used={svc.this_week?.used ?? 0}
                    limit={svc.this_week?.limit}
                    percentUsed={svc.this_week?.percent_used}
                    warning={svc.warning}
                  />
                )}
                {svc.this_month?.limit != null && (
                  <UsageMeter
                    label="This month"
                    used={svc.this_month?.used ?? 0}
                    limit={svc.this_month?.limit}
                    percentUsed={svc.this_month?.percent_used}
                    warning={svc.warning}
                  />
                )}
                {svc.today?.limit == null && svc.this_week?.limit == null && (
                  <UsageMeter
                    label="Today"
                    used={svc.today?.used ?? 0}
                    limit={null}
                    percentUsed={null}
                    warning={svc.warning}
                  />
                )}
                {svc.notes && (
                  <p className="quota-service-note mono">{svc.notes}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
