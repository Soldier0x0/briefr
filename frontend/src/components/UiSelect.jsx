import './UiSelect.css'

export default function UiSelect({
  value,
  onChange,
  options = [],
  label,
  id,
  className = '',
  disabled = false,
}) {
  const selectId = id || (label ? label.replace(/\s+/g, '-').toLowerCase() : undefined)
  return (
    <label className={`ui-select-field ${className}`.trim()}>
      {label ? <span className="ui-select-label">{label}</span> : null}
      <select
        id={selectId}
        className="ui-select admin-select"
        value={value}
        disabled={disabled}
        onChange={e => onChange(Number(e.target.value))}
      >
        {options.map(opt => (
          <option key={opt} value={opt}>{opt}px</option>
        ))}
      </select>
    </label>
  )
}
