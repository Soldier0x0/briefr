const TONE_CLASS = {
  'color-green': 'admin-stat-card--ok',
  'color-amber': 'admin-stat-card--warn',
  'color-red': 'admin-stat-card--err',
}

export default function StatCard({ label, value, subLabel, colorClass, valueStyle }) {
  const tone = TONE_CLASS[colorClass] || ''
  return (
    <div className={`stat-card admin-stat-card ${tone}`}>
      <div className="stat-card-label admin-stat-card-label">{label}</div>
      <div
        className={`stat-card-value admin-stat-card-value ${colorClass || ''}`}
        style={valueStyle}
      >
        {value ?? '—'}
      </div>
      {subLabel && <div className="stat-card-sub admin-stat-card-sub">{subLabel}</div>}
    </div>
  )
}
