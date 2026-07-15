import { useEffect, useId, useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { format } from 'date-fns'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import Button from './Button.jsx'
import Select from './Select.jsx'
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
    return {
      date: now,
      hours: now.getHours(),
      minutes: now.getMinutes(),
    }
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    const now = new Date()
    return {
      date: now,
      hours: now.getHours(),
      minutes: now.getMinutes(),
    }
  }
  return {
    date,
    hours: date.getHours(),
    minutes: date.getMinutes(),
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
 * Dark-themed date + time picker (react-day-picker + Radix dropdown).
 * Value/onChange use the same datetime-local string format as native inputs.
 */
export default function DateTimePicker({
  value = '',
  onChange,
  placeholder = 'Select date & time…',
  ariaLabel = 'Select date and time',
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

  useEffect(() => {
    if (!open) return
    const next = partsFromValue(value)
    setDraftDate(next.date)
    setDraftHours(next.hours)
    setDraftMinutes(next.minutes)
  }, [open, value])

  function emit(date, hours, minutes) {
    onChange?.(combineDateTime(date, hours, minutes))
  }

  function handleDaySelect(day) {
    if (!day) return
    setDraftDate(day)
    emit(day, draftHours, draftMinutes)
  }

  function handleHoursChange(nextHours) {
    const hours = Number(nextHours)
    setDraftHours(hours)
    emit(draftDate, hours, draftMinutes)
  }

  function handleMinutesChange(nextMinutes) {
    const minutes = Number(nextMinutes)
    setDraftMinutes(minutes)
    emit(draftDate, draftHours, minutes)
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
        <div className="ui-datetime-picker-time" role="group" aria-label="Time">
          <Select
            id={`${listId}-hour`}
            className="ui-datetime-picker-time-select"
            value={String(draftHours)}
            onValueChange={(val) => handleHoursChange(val)}
            options={Array.from({ length: 24 }, (_, hour) => ({
              value: String(hour),
              label: String(hour).padStart(2, '0'),
            }))}
            aria-label="Hour"
          />
          <span className="ui-datetime-picker-time-sep mono" aria-hidden="true">
            :
          </span>
          <Select
            id={`${listId}-minute`}
            className="ui-datetime-picker-time-select"
            value={String(draftMinutes)}
            onValueChange={(val) => handleMinutesChange(val)}
            options={Array.from({ length: 60 }, (_, minute) => ({
              value: String(minute),
              label: String(minute).padStart(2, '0'),
            }))}
            aria-label="Minute"
          />
        </div>
        <div className="ui-datetime-picker-actions">
          {clearable && (
            <Button type="button" variant="ghost" size="sm" onClick={handleClear}>
              Clear
            </Button>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
            Done
          </Button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
