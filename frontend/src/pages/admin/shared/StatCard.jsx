const ACCENT_COLORS = {
  'color-green': 'var(--green)',
  'color-amber': 'var(--amber)',
  'color-red': 'var(--red)',
}

export default function StatCard({ label, value, subLabel, colorClass, valueStyle }) {
  const accent = ACCENT_COLORS[colorClass]
  return (
    <div className="stat-card" style={accent ? { borderLeft: `3px solid ${accent}` } : undefined}>
      <div className="stat-card-label">{label}</div>
      <div className={`stat-card-value ${colorClass || ''}`} style={valueStyle}>{value ?? '—'}</div>
      {subLabel && <div className="stat-card-sub">{subLabel}</div>}
    </div>
  )
}
