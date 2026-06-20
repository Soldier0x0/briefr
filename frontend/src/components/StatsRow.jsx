import './StatsRow.css'

function StatCell({ value, label, variant, loading, onClick, interactive }) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      className={`stat-cell stat-${variant}${interactive ? ' stat-cell-interactive' : ''}`}
      aria-label={`${label}: ${value ?? 'loading'}`}
      onClick={onClick}
    >
      <div className="stat-number">
        {loading ? <span className="stat-skeleton" aria-hidden="true" /> : (value ?? '--')}
      </div>
      <div className="stat-label">{label}</div>
    </Tag>
  )
}

export default function StatsRow({ stats, showAiAlerts, onAiAlertsClick }) {
  const loading = !stats
  const aiCount = stats?.ai_ml_alerts ?? 0
  const showAi = showAiAlerts && (loading || aiCount > 0)

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
      />
      <StatCell
        value={stats?.high?.toLocaleString()}
        label="HIGH"
        variant="amber"
        loading={loading}
      />
      <StatCell
        value={stats?.kev_count?.toLocaleString()}
        label="EXPLOITED IN WILD"
        variant="red"
        loading={loading}
      />
      <StatCell
        value={stats?.patched?.toLocaleString()}
        label="PATCHES AVAILABLE"
        variant="green"
        loading={loading}
      />
      {showAi && (
        <StatCell
          value={aiCount.toLocaleString()}
          label="AI/ML ALERTS"
          variant="ai"
          loading={loading}
          onClick={onAiAlertsClick}
          interactive
        />
      )}
    </section>
  )
}
