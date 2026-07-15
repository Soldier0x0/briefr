import { useEffect, useId, useState } from 'react'
import { DateTimeRangeField, Select } from './ui/index.js'
import { parseDatetimeLocalToIso, toDatetimeLocalValue } from './timeWindowDateUtils.js'
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
    const since = parseDatetimeLocalToIso(sinceLocal)
    const until = parseDatetimeLocalToIso(untilLocal) || new Date().toISOString()
    onChange?.({ mode: 'custom', since, until })
  }

  function handleSelectChange(next) {
    setSelectValue(next)
    if (next === CUSTOM_VALUE) {
      emitCustom(customSince, customUntil)
    } else {
      emitPreset(next)
    }
  }

  return (
    <div className="time-window-picker" role="group" aria-label={ariaLabel}>
      <label htmlFor={selectId} className="sr-only">{ariaLabel}</label>
      <Select
        id={selectId}
        className="time-window-select mono"
        value={selectValue}
        onChange={handleSelectChange}
        aria-label={ariaLabel}
        options={[
          ...presets.map(p => ({ value: p.id, label: p.label })),
          { value: CUSTOM_VALUE, label: 'Custom range…' },
        ]}
      />
      {selectValue === CUSTOM_VALUE && (
        <DateTimeRangeField
          className="time-window-datetime-range"
          startValue={customSince}
          endValue={customUntil}
          onStartChange={(next) => {
            setCustomSince(next)
            emitCustom(next, customUntil)
          }}
          onEndChange={(next) => {
            setCustomUntil(next)
            emitCustom(customSince, next)
          }}
          startPlaceholder="From…"
          endPlaceholder="To…"
          clearable={false}
        />
      )}
    </div>
  )
}
