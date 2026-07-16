import DateTimePicker from './DateTimePicker.jsx'
import './DateTimeRangeField.css'

/**
 * Dual-input datetime range (MUI MultiInputDateTimeRangeField layout) without MUI Pro.
 * Start and end fields side-by-side with a separator.
 */
export default function DateTimeRangeField({
  startValue = '',
  endValue = '',
  onStartChange,
  onEndChange,
  startPlaceholder = 'Start',
  endPlaceholder = 'End',
  disabled = false,
  className = '',
  clearable = true,
}) {
  return (
    <div
      className={['ui-datetime-range-field', className].filter(Boolean).join(' ')}
      role="group"
      aria-label="Date and time range"
    >
      <DateTimePicker
        className="ui-datetime-range-start"
        value={startValue}
        onChange={onStartChange}
        placeholder={startPlaceholder}
        timeLabel="Start time"
        ariaLabel="Range start date and time"
        disabled={disabled}
        clearable={clearable}
      />
      <span className="ui-datetime-range-sep mono" aria-hidden="true">
        –
      </span>
      <DateTimePicker
        className="ui-datetime-range-end"
        value={endValue}
        onChange={onEndChange}
        placeholder={endPlaceholder}
        timeLabel="End time"
        ariaLabel="Range end date and time"
        disabled={disabled}
        clearable={clearable}
      />
    </div>
  )
}
