import { useEffect, useId, useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { format } from 'date-fns'
import { ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import Button from './Button.jsx'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from './DropdownMenu.jsx'
import { toDatetimeLocalValue } from '../timeWindowDateUtils.js'
import 'react-day-picker/style.css'
import './DateTimePicker.css'

const DISPLAY_FMT = 'yyyy-MM-dd HH:mm'

function partsFromValue(value) {
  if (!value) {
    const now = new Date()
    return { date: now, hours: now.getHours(), minutes: now.getMinutes(), seconds: 0 }
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    const now = new Date()
    return { date: now, hours: now.getHours(), minutes: now.getMinutes(), seconds: 0 }
  }
  return {
    date,
    hours: date.getHours(),
    minutes: date.getMinutes(),
    seconds: date.getSeconds(),
  }
}

function toTimeInputValue(hours, minutes, seconds = 0) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
}

function fromTimeInputValue(value) {
  if (!value) return { hours: 0, minutes: 0, seconds: 0 }
  const [h, m, s] = value.split(':')
  return {
    hours: Number.parseInt(h, 10) || 0,
    minutes: Number.parseInt(m, 10) || 0,
    seconds: Number.parseInt(s, 10) || 0,
  }
}

function combineDateTime(date, hours, minutes) {
  const next = new Date(date)
  next.setHours(hours, minutes, 0, 0)
  return toDatetimeLocalValue(next)
}

function displayLabel(value, placeholder) {
  if (!value) return placeholder
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return placeholder
  return format(date, DISPLAY_FMT)
}

/**
 * shadcn-style date + time picker (option A): card calendar + native time footer.
 * Value/onChange use datetime-local string format (minute precision).
 */
export default function DateTimePicker({
  value = '',
  onChange,
  placeholder = 'Select date & time…',
  ariaLabel = 'Select date and time',
  timeLabel = 'Time',
  className = '',
  disabled = false,
  clearable = true,
}) {
  const listId = useId()
  const [open, setOpen] = useState(false)
  const initial = partsFromValue(value)
  const [draftDate, setDraftDate] = useState(initial.date)
  const [draftHours, setDraftHours] = useState(initial.hours)
  const [draftMinutes, setDraftMinutes] = useState(initial.minutes)
  const [draftSeconds, setDraftSeconds] = useState(initial.seconds)

  useEffect(() => {
    if (!open) return
    const next = partsFromValue(value)
    setDraftDate(next.date)
    setDraftHours(next.hours)
    setDraftMinutes(next.minutes)
    setDraftSeconds(next.seconds)
  }, [open, value])

  function emit(date, hours, minutes) {
    onChange?.(combineDateTime(date, hours, minutes))
  }

  function handleDaySelect(day) {
    if (!day) return
    setDraftDate(day)
    emit(day, draftHours, draftMinutes)
  }

  function handleTimeInput(nextValue) {
    const { hours, minutes, seconds } = fromTimeInputValue(nextValue)
    setDraftHours(hours)
    setDraftMinutes(minutes)
    setDraftSeconds(seconds)
    emit(draftDate, hours, minutes)
  }

  function handleClear() {
    onChange?.('')
    setOpen(false)
  }

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
          <span className={value ? '' : 'ui-datetime-picker-placeholder'}>
            {displayLabel(value, placeholder)}
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="ui-datetime-picker-content"
        align="start"
        sideOffset={6}
        onCloseAutoFocus={(event) => event.preventDefault()}
      >
        <div className="ui-datetime-picker-card">
          <div className="ui-datetime-picker-body">
            <DayPicker
              mode="single"
              selected={draftDate}
              onSelect={handleDaySelect}
              defaultMonth={draftDate}
              showOutsideDays
              className="ui-day-picker"
              classNames={{
                months: 'ui-day-picker-months',
                month: 'ui-day-picker-month',
                month_caption: 'ui-day-picker-caption',
                caption_label: 'ui-day-picker-caption-label',
                nav: 'ui-day-picker-nav',
                button_previous: 'ui-day-picker-nav-btn',
                button_next: 'ui-day-picker-nav-btn',
                weekdays: 'ui-day-picker-weekdays',
                weekday: 'ui-day-picker-weekday',
                week: 'ui-day-picker-week',
                day: 'ui-day-picker-day',
                day_button: 'ui-day-picker-day-btn',
                selected: 'ui-day-picker-selected',
                today: 'ui-day-picker-today',
                outside: 'ui-day-picker-outside',
                disabled: 'ui-day-picker-disabled',
              }}
              components={{
                Chevron: ({ orientation, className: chevronClass, ...props }) => {
                  const Icon = orientation === 'left' ? ChevronLeft : ChevronRight
                  return <Icon size={15} strokeWidth={2} className={chevronClass} {...props} />
                },
              }}
            />
          </div>
          <div className="ui-datetime-picker-footer">
            <div className="ui-datetime-picker-field">
              <label className="ui-datetime-picker-field-label" htmlFor={`${listId}-time`}>
                {timeLabel}
              </label>
              <div className="ui-datetime-picker-time-input">
                <Clock size={15} className="ui-datetime-picker-clock-leading" aria-hidden="true" />
                <input
                  id={`${listId}-time`}
                  type="time"
                  step="1"
                  value={toTimeInputValue(draftHours, draftMinutes, draftSeconds)}
                  onChange={(e) => handleTimeInput(e.target.value)}
                  className="ui-datetime-picker-time-native"
                  aria-label={timeLabel}
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
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
