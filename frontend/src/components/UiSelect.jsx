import { Select } from './ui/index.js'
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
  const selectOptions = options.map((opt) => ({
    value: String(opt),
    label: `${opt}px`,
  }))

  const field = (
    <Select
      id={selectId}
      className={`ui-select ${className}`.trim()}
      value={String(value)}
      onChange={(v) => onChange(Number(v))}
      options={selectOptions}
      disabled={disabled}
    />
  )

  if (!label) return field

  return (
    <label className={`ui-select-field ${className}`.trim()}>
      <span className="ui-select-label">{label}</span>
      {field}
    </label>
  )
}
