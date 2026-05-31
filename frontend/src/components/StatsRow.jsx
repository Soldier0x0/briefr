import './StatsRow.css'

function StatCell({ value, label, variant, loading }) {
  return (
    <div className={`stat-cell stat-${variant}`} aria-label={`${label}: ${value ?? 'loading'}`}>
      <div className="stat-number">
        {loading ? <span className="stat-skeleton" aria-hidden="true" /> : (value ?? '--')}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export default function StatsRow({ stats }) {
  const loading = !stats

  return (
    <section className="stats-row" aria-label="CVE statistics summary">
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
    </section>
  )
}
