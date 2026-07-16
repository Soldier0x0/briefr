/** Shared datetime-local string helpers (YYYY-MM-DDTHH:mm:ss). */

function pad(n) {
  return String(n).padStart(2, '0')
}

export function parseDatetimeLocalToIso(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function toDatetimeLocalValue(isoOrDate) {
  if (!isoOrDate) return ''
  const date = isoOrDate instanceof Date ? isoOrDate : new Date(isoOrDate)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function partsFromDatetimeLocal(value) {
  const fallback = new Date()
  if (!value) {
    return {
      day: fallback.getDate(),
      month: fallback.getMonth() + 1,
      year: fallback.getFullYear(),
      hours: fallback.getHours(),
      minutes: fallback.getMinutes(),
      seconds: fallback.getSeconds(),
    }
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return {
      day: fallback.getDate(),
      month: fallback.getMonth() + 1,
      year: fallback.getFullYear(),
      hours: fallback.getHours(),
      minutes: fallback.getMinutes(),
      seconds: fallback.getSeconds(),
    }
  }
  return {
    day: date.getDate(),
    month: date.getMonth() + 1,
    year: date.getFullYear(),
    hours: date.getHours(),
    minutes: date.getMinutes(),
    seconds: date.getSeconds(),
  }
}

export function buildDatetimeLocalFromParts(parts) {
  const year = Number(parts.year) || new Date().getFullYear()
  const month = Number(parts.month) || 1
  let day = Number(parts.day) || 1
  const maxDay = daysInMonth(year, month)
  day = Math.min(Math.max(1, day), maxDay)
  const hours = Math.min(Math.max(0, Number(parts.hours) || 0), 23)
  const minutes = Math.min(Math.max(0, Number(parts.minutes) || 0), 59)
  const seconds = Math.min(Math.max(0, Number(parts.seconds) || 0), 59)
  const date = new Date(year, month - 1, day, hours, minutes, seconds)
  return toDatetimeLocalValue(date)
}

export function formatDatetimeDisplay(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const dd = pad(date.getDate())
  const mm = pad(date.getMonth() + 1)
  const yy = pad(date.getFullYear() % 100)
  return `${dd}-${mm}-${yy} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function daysInMonth(year, month) {
  return new Date(year, month, 0).getDate()
}

export const DATETIME_YEAR_MIN = 1999
export const DATETIME_YEAR_MAX = new Date().getFullYear() + 1
