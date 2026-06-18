import { useEffect, useId, useState } from 'react'
import './TimeWindowPicker.css'

export const TIME_PRESETS = [
  { id: '6h', label: '6 hours', hours: 6 },
  { id: '12h', label: '12 hours', hours: 12 },
  { id: '24h', label: '24 hours', hours: 24 },
  { id: '2d', label: '2 days', hours: 48 },
  { id: '7d', label: '7 days', hours: 168 },
  { id: '30d', label: '30 days', hours: 720 },
  { id: '90d', label: '90 days', hours: 2160 },
]

const CUSTOM_VALUE = 'custom'

/** @typedef {{ mode: 'preset', presetId: string, hours: number } | { mode: 'custom', since: string, until: string }} TimeWindowValue */

export function hoursFromWindow(value) {
  if (!value) return 168
  if (value.mode === 'preset') return value.hours
  if (!value.since) return 168
  const sinceMs = new Date(value.since).getTime()
  const untilMs = value.until ? new Date(value.until).getTime() : Date.now()
  if (Number.isNaN(sinceMs) || Number.isNaN(untilMs)) return 168
  return Math.max(1, Math.round((untilMs - sinceMs) / 3600000))
}

export function defaultPresetWindow(presetId = '7d') {
  const preset = TIME_PRESETS.find(p => p.id === presetId) || TIME_PRESETS.find(p => p.id === '7d')
  return { mode: 'preset', presetId: preset.id, hours: preset.hours }
}

function toDatetimeLocalValue(isoOrDate) {
  const d = isoOrDate instanceof Date ? isoOrDate : new Date(isoOrDate)
  if (Number.isNaN(d.getTime())) return ''
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function defaultCustomSince() {
  const d = new Date()
  d.setDate(d.getDate() - 7)
  return toDatetimeLocalValue(d)
}

function defaultCustomUntil() {
  return toDatetimeLocalValue(new Date())
}

export default function TimeWindowPicker({
  value,
  onChange,
  ariaLabel = 'Select time window',
  presetIds = TIME_PRESETS.map(p => p.id),
}) {
  const selectId = useId()
  const presets = TIME_PRESETS.filter(p => presetIds.includes(p.id))
  const [selectValue, setSelectValue] = useState(() =>
    value?.mode === 'custom' ? CUSTOM_VALUE : (value?.presetId || presets[0]?.id || '7d')
  )
  const [customSince, setCustomSince] = useState(() =>
    value?.mode === 'custom' && value.since ? toDatetimeLocalValue(value.since) : defaultCustomSince()
  )
  const [customUntil, setCustomUntil] = useState(() =>
    value?.mode === 'custom' && value.until ? toDatetimeLocalValue(value.until) : defaultCustomUntil()
  )

  useEffect(() => {
    if (value?.mode === 'custom') {
      setSelectValue(CUSTOM_VALUE)
      if (value.since) setCustomSince(toDatetimeLocalValue(value.since))
      if (value.until) setCustomUntil(toDatetimeLocalValue(value.until))
    } else if (value?.presetId) {
      setSelectValue(value.presetId)
    }
  }, [value?.mode, value?.presetId, value?.since, value?.until])

  function emitPreset(presetId) {
    const preset = TIME_PRESETS.find(p => p.id === presetId)
    if (!preset) return
    onChange?.({ mode: 'preset', presetId: preset.id, hours: preset.hours })
  }

  function emitCustom(sinceLocal, untilLocal) {
    const since = sinceLocal ? new Date(sinceLocal).toISOString() : null
    const until = untilLocal ? new Date(untilLocal).toISOString() : new Date().toISOString()
    onChange?.({ mode: 'custom', since, until })
  }

  function handleSelectChange(e) {
    const next = e.target.value
    setSelectValue(next)
    if (next === CUSTOM_VALUE) {
      emitCustom(customSince, customUntil)
    } else {
      emitPreset(next)
    }
  }

  function handleSinceChange(e) {
    const next = e.target.value
    setCustomSince(next)
    emitCustom(next, customUntil)
  }

  function handleUntilChange(e) {
    const next = e.target.value
    setCustomUntil(next)
    emitCustom(customSince, next)
  }

  return (
    <div className="time-window-picker" role="group" aria-label={ariaLabel}>
      <label htmlFor={selectId} className="sr-only">{ariaLabel}</label>
      <select
        id={selectId}
        className="time-window-select mono"
        value={selectValue}
        onChange={handleSelectChange}
        aria-label={ariaLabel}
      >
        {presets.map(p => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
        <option value={CUSTOM_VALUE}>Custom range…</option>
      </select>
      {selectValue === CUSTOM_VALUE && (
        <div className="time-window-custom" aria-label="Custom date and time range">
          <label className="time-window-custom-field">
            <span className="time-window-custom-label mono">From</span>
            <input
              type="datetime-local"
              className="time-window-datetime mono"
              value={customSince}
              onChange={handleSinceChange}
              aria-label="Range start date and time"
            />
          </label>
          <label className="time-window-custom-field">
            <span className="time-window-custom-label mono">To</span>
            <input
              type="datetime-local"
              className="time-window-datetime mono"
              value={customUntil}
              onChange={handleUntilChange}
              aria-label="Range end date and time"
            />
          </label>
        </div>
      )}
    </div>
  )
}
