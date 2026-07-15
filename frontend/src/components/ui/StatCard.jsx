const TONE_CLASS = {
  'color-green': 'ui-stat-card--ok admin-stat-card--ok',
  'color-amber': 'ui-stat-card--warn admin-stat-card--warn',
  'color-red': 'ui-stat-card--err admin-stat-card--err',
}

/**
 * Metric tile primitive (E3-7). Keeps legacy admin/ARCH class hooks during migration.
 * @param {object} props
 * @param {string} props.label
 * @param {React.ReactNode} props.value
 * @param {string} [props.subLabel]
 * @param {string} [props.subLabelTitle]
 * @param {'color-green'|'color-amber'|'color-red'} [props.colorClass]
 * @param {object} [props.valueStyle]
 * @param {boolean} [props.plain=false] ARCH overview uses plain surface without admin skin
 */
export default function StatCard({
  label,
  value,
  subLabel,
  subLabelTitle,
  colorClass,
  valueStyle,
  plain = false,
}) {
  const tone = TONE_CLASS[colorClass] || ''
  const rootClass = plain
    ? `ui-stat-card stat-card sa-stat-card ${tone}`
    : `ui-stat-card stat-card admin-stat-card ${tone}`
  return (
    <div className={rootClass}>
      <div className="ui-stat-card-label stat-card-label admin-stat-card-label">{label}</div>
      <div
        className={`ui-stat-card-value stat-card-value admin-stat-card-value ${colorClass || ''}`}
        style={valueStyle}
      >
        {value ?? '—'}
      </div>
      {subLabel && (
        <div
          className="ui-stat-card-sub stat-card-sub admin-stat-card-sub"
          title={subLabelTitle || (subLabel.length > 36 ? subLabel : undefined)}
        >
          {subLabel}
        </div>
      )}
    </div>
  )
}
