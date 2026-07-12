import { ingestLogUrl } from '../utils/adminLinks.js'
import ControlTooltip from './ControlTooltip.jsx'
import './StatsRow.css'

function formatDelta(delta) {
  if (delta == null || Number.isNaN(delta)) return null
  if (delta > 0) return `+${delta}`
  return String(delta)
}

function StatCell({
  value,
  label,
  variant,
  loading,
  onClick,
  interactive,
  explain,
  delta,
}) {
  const Tag = onClick ? 'button' : 'div'
  const deltaText = formatDelta(delta)
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      className={`stat-cell stat-${variant}${interactive ? ' stat-cell-interactive' : ''}`}
      aria-label={`${label}: ${value ?? 'loading'}${deltaText ? `, ${deltaText} vs prior 24h` : ''}`}
      onClick={onClick}
    >
      <div className="stat-number-row">
        <div className="stat-number">
          {loading ? <span className="stat-skeleton" aria-hidden="true" /> : (value ?? '--')}
        </div>
        {/* QA-P2-1: a flat (0) delta rendered as a tiny muted number at the
            same baseline as the large stat number reads as noise, not a
            value — omit it entirely rather than show a number with nothing
            to say. Nonzero deltas are unaffected. */}
        {!loading && deltaText != null && delta !== 0 && (
          <span
            className={`stat-delta mono stat-delta--${delta > 0 ? 'up' : 'down'}`}
            title="Change in publications vs prior 24h"
          >
            {deltaText}
          </span>
        )}
      </div>
      <div className="stat-label">
        {explain ? (
          <ControlTooltip text={explain}>
            <span tabIndex={0} className="stat-label-text">{label}</span>
          </ControlTooltip>
        ) : (
          label
        )}
      </div>
    </Tag>
  )
}

export default function StatsRow({
  stats,
  error,
  errorRequestId,
  onRetry,
  showAiAlerts,
  onAiAlertsClick,
  onStatTileClick,
}) {
  const loading = !stats
  const aiCount = stats?.ai_ml_alerts ?? 0
  const showAi = showAiAlerts && (loading || aiCount > 0)

  if (error && loading) {
    return (
      <section className="stats-row stats-row-error" aria-label="CVE statistics summary" role="alert">
        <span>
          {error}
          {errorRequestId && (
            <>
              {' '}
              (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                ref: {errorRequestId}
              </a>)
            </>
          )}
        </span>
        <button type="button" className="stats-row-retry-btn" onClick={onRetry}>
          Retry
        </button>
      </section>
    )
  }

  return (
    <section
      className={`stats-row${showAi ? ' stats-row--five' : ''}`}
      aria-label="CVE statistics summary"
    >
      <StatCell
        value={stats?.critical?.toLocaleString()}
        label="CRITICAL"
        variant="red"
        loading={loading}
        delta={stats?.critical_delta}
        interactive
        onClick={() => onStatTileClick?.('critical')}
      />
      <StatCell
        value={stats?.high?.toLocaleString()}
        label="HIGH"
        variant="amber"
        loading={loading}
        delta={stats?.high_delta}
        interactive
        onClick={() => onStatTileClick?.('high')}
      />
      <StatCell
        value={stats?.kev_count?.toLocaleString()}
        label="KEV (EXPLOITED)"
        variant="red"
        loading={loading}
        delta={stats?.kev_delta}
        interactive
        onClick={() => onStatTileClick?.('kev')}
        explain="CVEs on CISA's Known Exploited Vulnerabilities (KEV) catalog — confirmed active exploitation in the wild, not theoretical risk alone."
      />
      <StatCell
        value={stats?.patched?.toLocaleString()}
        label="PATCHES AVAILABLE"
        variant="green"
        loading={loading}
        delta={stats?.patched_delta}
        interactive
        onClick={() => onStatTileClick?.('patched')}
      />
      {showAi && (
        <StatCell
          value={aiCount.toLocaleString()}
          label="AI/ML IN STACK"
          variant="ai"
          loading={loading}
          explain="CVE count matching AI/ML frameworks in your My Stack. Click to filter the feed."
          onClick={onAiAlertsClick}
          interactive
        />
      )}
    </section>
  )
}
