// Timezone utilities shared across Header, CVECard, and report generators

export const COMMON_TIMEZONES = [
  { tz: 'UTC',                 label: 'UTC',              search: 'utc' },
  { tz: 'Asia/Kolkata',        label: 'Asia/Kolkata',     search: 'india kolkata ist' },
  { tz: 'America/New_York',    label: 'America/New_York', search: 'new york eastern est edt usa' },
  { tz: 'America/Los_Angeles', label: 'America/LA',       search: 'los angeles pacific pst pdt usa' },
  { tz: 'America/Chicago',     label: 'America/Chicago',  search: 'chicago central cst cdt usa' },
  { tz: 'Europe/London',       label: 'Europe/London',    search: 'london gmt bst uk england' },
  { tz: 'Europe/Berlin',       label: 'Europe/Berlin',    search: 'berlin cet cest germany' },
  { tz: 'Europe/Paris',        label: 'Europe/Paris',     search: 'paris cet cest france' },
  { tz: 'Asia/Tokyo',          label: 'Asia/Tokyo',       search: 'tokyo jst japan' },
  { tz: 'Asia/Singapore',      label: 'Asia/Singapore',   search: 'singapore sgt' },
  { tz: 'Asia/Dubai',          label: 'Asia/Dubai',       search: 'dubai gst uae gulf' },
  { tz: 'Australia/Sydney',    label: 'Australia/Sydney', search: 'sydney aest aedt australia' },
  { tz: 'America/Sao_Paulo',   label: 'America/Sao Paulo',search: 'sao paulo brazil brt' },
]

export const TIMEZONES_BY_CONTINENT = [
  { continent: 'UTC', zones: [{ tz: 'UTC', label: 'UTC' }] },
  {
    continent: 'Africa',
    zones: [
      { tz: 'Africa/Cairo', label: 'Africa/Cairo' },
      { tz: 'Africa/Johannesburg', label: 'Africa/Johannesburg' },
      { tz: 'Africa/Lagos', label: 'Africa/Lagos' },
      { tz: 'Africa/Nairobi', label: 'Africa/Nairobi' },
    ],
  },
  {
    continent: 'America',
    zones: [
      { tz: 'America/New_York', label: 'America/New York' },
      { tz: 'America/Chicago', label: 'America/Chicago' },
      { tz: 'America/Denver', label: 'America/Denver' },
      { tz: 'America/Los_Angeles', label: 'America/Los Angeles' },
      { tz: 'America/Toronto', label: 'America/Toronto' },
      { tz: 'America/Mexico_City', label: 'America/Mexico City' },
      { tz: 'America/Sao_Paulo', label: 'America/Sao Paulo' },
    ],
  },
  {
    continent: 'Asia',
    zones: [
      { tz: 'Asia/Kolkata', label: 'Asia/Kolkata' },
      { tz: 'Asia/Dubai', label: 'Asia/Dubai' },
      { tz: 'Asia/Singapore', label: 'Asia/Singapore' },
      { tz: 'Asia/Tokyo', label: 'Asia/Tokyo' },
      { tz: 'Asia/Shanghai', label: 'Asia/Shanghai' },
      { tz: 'Asia/Hong_Kong', label: 'Asia/Hong Kong' },
      { tz: 'Asia/Seoul', label: 'Asia/Seoul' },
      { tz: 'Asia/Bangkok', label: 'Asia/Bangkok' },
      { tz: 'Asia/Tel_Aviv', label: 'Asia/Tel Aviv' },
    ],
  },
  {
    continent: 'Australia/Oceania',
    zones: [
      { tz: 'Australia/Sydney', label: 'Australia/Sydney' },
      { tz: 'Australia/Perth', label: 'Australia/Perth' },
      { tz: 'Pacific/Auckland', label: 'Pacific/Auckland' },
    ],
  },
  {
    continent: 'Europe',
    zones: [
      { tz: 'Europe/London', label: 'Europe/London' },
      { tz: 'Europe/Paris', label: 'Europe/Paris' },
      { tz: 'Europe/Berlin', label: 'Europe/Berlin' },
      { tz: 'Europe/Madrid', label: 'Europe/Madrid' },
      { tz: 'Europe/Rome', label: 'Europe/Rome' },
      { tz: 'Europe/Moscow', label: 'Europe/Moscow' },
    ],
  },
]

export function getTzAbbr(tz, date = new Date()) {
  if (tz === 'UTC') return 'UTC'
  try {
    const parts = Intl.DateTimeFormat('en', {
      timeZone: tz,
      timeZoneName: 'short',
    }).formatToParts(date)
    return parts.find(p => p.type === 'timeZoneName')?.value || tz.split('/').pop()
  } catch {
    return tz.split('/').pop()
  }
}

export function formatTime(date, tz) {
  try {
    return new Intl.DateTimeFormat('en-GB', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(date)
  } catch {
    return '--:--:--'
  }
}

export function formatDateTime(date, tz) {
  try {
    const datePart = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(date)
    return `${datePart} ${formatTime(date, tz)}`
  } catch {
    return date.toISOString()
  }
}

// Absolute timestamp for CVECard hover tooltip
// e.g. "2026-05-31 21:03 IST"
export function formatAbsolute(isoString, tz) {
  if (!isoString) return ''
  try {
    const date = new Date(isoString)
    const datePart = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(date)
    const timePart = new Intl.DateTimeFormat('en-GB', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date)
    const abbr = getTzAbbr(tz, date)
    return `${datePart} ${timePart} ${abbr}`
  } catch {
    return isoString
  }
}

// For copy-report and digest: "2026-06-01 00:03:01 IST (18:33:01 UTC)"
export function getReportTimestamp() {
  const now = new Date()
  const tz = localStorage.getItem('briefr_timezone') || 'UTC'
  if (tz === 'UTC') {
    return formatDateTime(now, 'UTC') + ' UTC'
  }
  const local = formatDateTime(now, tz)
  const abbr  = getTzAbbr(tz, now)
  const utc   = formatTime(now, 'UTC')
  return `${local} ${abbr} (${utc} UTC)`
}

// Dispatch when timezone changes so App can propagate via props
export function setTimezone(tz) {
  localStorage.setItem('briefr_timezone', tz)
  window.dispatchEvent(new CustomEvent('briefr-timezone-change', { detail: tz }))
}
