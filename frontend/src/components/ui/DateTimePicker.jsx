import { useEffect, useId, useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { format } from 'date-fns'
import Button from './Button.jsx'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from './DropdownMenu.jsx'
import { toDatetimeLocalValue } from '../timeWindowDateUtils.js'
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
 * Dark-themed date + time picker (react-day-picker calendar in a Radix dropdown).
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
          className="ui-datetime-picker-calendar"
          showOutsideDays
        />
        <div className="ui-datetime-picker-time" role="group" aria-label="Time">
          <label className="ui-datetime-picker-time-label" htmlFor={`${listId}-hour`}>
            Hour
          </label>
          <select
            id={`${listId}-hour`}
            className="ui-datetime-picker-time-select mono"
            value={draftHours}
            onChange={(e) => handleHoursChange(e.target.value)}
            aria-label="Hour"
          >
            {Array.from({ length: 24 }, (_, hour) => (
              <option key={hour} value={hour}>
                {String(hour).padStart(2, '0')}
              </option>
            ))}
          </select>
          <span className="ui-datetime-picker-time-sep mono" aria-hidden="true">
            :
          </span>
          <label className="ui-datetime-picker-time-label" htmlFor={`${listId}-minute`}>
            Min
          </label>
          <select
            id={`${listId}-minute`}
            className="ui-datetime-picker-time-select mono"
            value={draftMinutes}
            onChange={(e) => handleMinutesChange(e.target.value)}
            aria-label="Minute"
          >
            {Array.from({ length: 60 }, (_, minute) => (
              <option key={minute} value={minute}>
                {String(minute).padStart(2, '0')}
              </option>
            ))}
          </select>
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
