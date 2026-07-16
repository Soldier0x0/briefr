import { useEffect, useId, useMemo, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import Button from './Button.jsx'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from './DropdownMenu.jsx'
import {
  DATETIME_YEAR_MAX,
  DATETIME_YEAR_MIN,
  buildDatetimeLocalFromParts,
  daysInMonth,
  formatDatetimeDisplay,
  partsFromDatetimeLocal,
} from '../timeWindowDateUtils.js'
import './DateTimePicker.css'

function rangeOptions(count, start = 0, padWidth = 2) {
  return Array.from({ length: count }, (_, i) => {
    const value = start + i
    const label = String(value).padStart(padWidth, '0')
    return { value: String(value), label }
  })
}

const DAY_OPTIONS = rangeOptions(31, 1)
const MONTH_OPTIONS = rangeOptions(12, 1)
const HOUR_OPTIONS = rangeOptions(24, 0)
const MINUTE_OPTIONS = rangeOptions(60, 0)
const SECOND_OPTIONS = rangeOptions(60, 0)

function yearOptions() {
  const out = []
  for (let year = DATETIME_YEAR_MAX; year >= DATETIME_YEAR_MIN; year -= 1) {
    out.push({ value: String(year), label: String(year).slice(-2) })
  }
  return out
}

function DateTimeSelect({ id, label, value, options, onChange, disabled }) {
  return (
    <label className="ui-datetime-select-field">
      <span className="ui-datetime-select-label mono">{label}</span>
      <span className="ui-datetime-select-wrap">
        <select
          id={id}
          className="ui-datetime-select mono"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          aria-label={label}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown size={12} className="ui-datetime-select-chevron" aria-hidden="true" />
      </span>
    </label>
  )
}

/**
 * Simple datetime picker: DD-MM-YY HH:mm:ss display with dropdown selects.
 * Value/onChange use datetime-local string format (second precision).
 */
export default function DateTimePicker({
  value = '',
  onChange,
  placeholder = 'DD-MM-YY HH:mm:ss',
  ariaLabel = 'Select date and time',
  className = '',
  disabled = false,
  clearable = true,
}) {
  const baseId = useId()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(() => partsFromDatetimeLocal(value))
  const yearOptionsMemo = useMemo(() => yearOptions(), [])

  useEffect(() => {
    if (!open) return
    setDraft(partsFromDatetimeLocal(value))
  }, [open, value])

  const maxDay = daysInMonth(draft.year, draft.month)
  const dayOptions = useMemo(
    () => DAY_OPTIONS.filter((opt) => Number(opt.value) <= maxDay),
    [maxDay],
  )

  function emit(nextParts) {
    const clamped = { ...nextParts }
    if (Number(clamped.day) > maxDay) {
      clamped.day = maxDay
    }
    setDraft(clamped)
    onChange?.(buildDatetimeLocalFromParts(clamped))
  }

  function updateField(field, nextValue) {
    emit({ ...draft, [field]: nextValue })
  }

  function handleClear() {
    onChange?.('')
    setOpen(false)
  }

  const display = formatDatetimeDisplay(value)
  const triggerClass = ['ui-datetime-picker-trigger', className].filter(Boolean).join(' ')

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild disabled={disabled}>
        <button
          type="button"
          className={triggerClass}
          aria-label={ariaLabel}
          disabled={disabled}
        >
          <span className={display ? 'ui-datetime-picker-value' : 'ui-datetime-picker-placeholder'}>
            {display || placeholder}
          </span>
          <ChevronDown size={14} className="ui-datetime-picker-chevron" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="ui-datetime-picker-content"
        align="start"
        sideOffset={6}
        onCloseAutoFocus={(event) => event.preventDefault()}
      >
        <div className="ui-datetime-picker-panel">
          <div className="ui-datetime-picker-section">
            <p className="ui-datetime-picker-section-title mono">Date</p>
            <div className="ui-datetime-picker-grid ui-datetime-picker-grid--date">
              <DateTimeSelect
                id={`${baseId}-day`}
                label="DD"
                value={String(Math.min(draft.day, maxDay))}
                options={dayOptions}
                onChange={(v) => updateField('day', Number(v))}
                disabled={disabled}
              />
              <DateTimeSelect
                id={`${baseId}-month`}
                label="MM"
                value={String(draft.month)}
                options={MONTH_OPTIONS}
                onChange={(v) => updateField('month', Number(v))}
                disabled={disabled}
              />
              <DateTimeSelect
                id={`${baseId}-year`}
                label="YY"
                value={String(draft.year)}
                options={yearOptionsMemo}
                onChange={(v) => updateField('year', Number(v))}
                disabled={disabled}
              />
            </div>
          </div>
          <div className="ui-datetime-picker-section">
            <p className="ui-datetime-picker-section-title mono">Time</p>
            <div className="ui-datetime-picker-grid ui-datetime-picker-grid--time">
              <DateTimeSelect
                id={`${baseId}-hour`}
                label="HH"
                value={String(draft.hours)}
                options={HOUR_OPTIONS}
                onChange={(v) => updateField('hours', Number(v))}
                disabled={disabled}
              />
              <DateTimeSelect
                id={`${baseId}-minute`}
                label="mm"
                value={String(draft.minutes)}
                options={MINUTE_OPTIONS}
                onChange={(v) => updateField('minutes', Number(v))}
                disabled={disabled}
              />
              <DateTimeSelect
                id={`${baseId}-second`}
                label="ss"
                value={String(draft.seconds)}
                options={SECOND_OPTIONS}
                onChange={(v) => updateField('seconds', Number(v))}
                disabled={disabled}
              />
            </div>
          </div>
          {clearable && (
            <div className="ui-datetime-picker-actions">
              <Button type="button" variant="ghost" size="sm" onClick={handleClear}>
                Clear
              </Button>
            </div>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
