// Timezone utilities shared across Header, CVECard, and report generators

import { getCachedUserPreferences, saveUserPreferences } from './userPreferences.js'

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

/** Fixed abbreviations (no DST). */
const TZ_ABBR_FIXED = {
  UTC: 'UTC',
  'Asia/Kolkata': 'IST',
  'Asia/Tokyo': 'JST',
  'Asia/Singapore': 'SGT',
  'Asia/Dubai': 'GST',
  'Asia/Shanghai': 'CST',
  'Asia/Hong_Kong': 'HKT',
  'Asia/Seoul': 'KST',
}

/** [standard, daylight] abbreviations when the zone observes DST. */
const TZ_ABBR_DST = {
  'America/New_York': ['EST', 'EDT'],
  'America/Los_Angeles': ['PST', 'PDT'],
  'America/Chicago': ['CST', 'CDT'],
  'America/Denver': ['MST', 'MDT'],
  'America/Toronto': ['EST', 'EDT'],
  'Europe/London': ['GMT', 'BST'],
  'Europe/Berlin': ['CET', 'CEST'],
  'Europe/Paris': ['CET', 'CEST'],
  'Europe/Madrid': ['CET', 'CEST'],
  'Europe/Rome': ['CET', 'CEST'],
  'Australia/Sydney': ['AEST', 'AEDT'],
  'Pacific/Auckland': ['NZST', 'NZDT'],
}

function tzOffsetMinutes(tz, date = new Date()) {
  try {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en', {
        timeZone: tz,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
        .formatToParts(date)
        .filter(p => p.type !== 'literal')
        .map(p => [p.type, Number(p.value)])
    )
    const asUtc = Date.UTC(
      parts.year,
      parts.month - 1,
      parts.day,
      parts.hour,
      parts.minute,
      parts.second
    )
    return Math.round((asUtc - date.getTime()) / 60000)
  } catch {
    return 0
  }
}

function dstAbbr(tz, pair, date = new Date()) {
  const year = date.getUTCFullYear()
  const jan = tzOffsetMinutes(tz, new Date(Date.UTC(year, 0, 15, 12)))
  const jul = tzOffsetMinutes(tz, new Date(Date.UTC(year, 6, 15, 12)))
  const current = tzOffsetMinutes(tz, date)
  const unique = [...new Set([jan, jul])]
  if (unique.length < 2) return pair[0]
  const stdOffset = Math.min(...unique)
  return current === stdOffset ? pair[0] : pair[1]
}

/** UTC offset label, e.g. "+05:30", "-04:00", "+00:00". */
export function getTzOffsetLabel(tz, date = new Date()) {
  if (tz === 'UTC') return '+00:00'
  const mins = tzOffsetMinutes(tz, date)
  const sign = mins >= 0 ? '+' : '-'
  const abs = Math.abs(mins)
  const h = String(Math.floor(abs / 60)).padStart(2, '0')
  const m = String(abs % 60).padStart(2, '0')
  return `${sign}${h}:${m}`
}

export function getTzAbbr(tz, date = new Date()) {
  if (TZ_ABBR_FIXED[tz]) return TZ_ABBR_FIXED[tz]
  const pair = TZ_ABBR_DST[tz]
  if (pair) return dstAbbr(tz, pair, date)
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
  const tz = getTimezone()
  if (tz === 'UTC') {
    return formatDateTime(now, 'UTC') + ' UTC'
  }
  const local = formatDateTime(now, tz)
  const abbr  = getTzAbbr(tz, now)
  const utc   = formatTime(now, 'UTC')
  return `${local} ${abbr} (${utc} UTC)`
}

// Dispatch when timezone changes so App can propagate via props
export function getTimezone() {
  return getCachedUserPreferences().timezone || 'UTC'
}

export async function setTimezone(tz) {
  await saveUserPreferences({}, tz)
}
