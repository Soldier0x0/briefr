export default function StatCard({ label, value, subLabel, colorClass, valueStyle }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className={`stat-card-value ${colorClass || ''}`} style={valueStyle}>{value ?? '—'}</div>
      {subLabel && <div className="stat-card-sub">{subLabel}</div>}
    </div>
  )
}
