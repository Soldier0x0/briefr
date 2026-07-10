/** Parse YYYY-MM-DD or ISO due date at UTC noon; null when invalid. */
export function parseDueDate(dueDate) {
  if (!dueDate) return null
  const raw = String(dueDate).includes('T') ? dueDate : `${String(dueDate).slice(0, 10)}T12:00:00Z`
  const due = new Date(raw)
  return Number.isNaN(due.getTime()) ? null : due
}

/** Days until a YYYY-MM-DD (or ISO) KEV due date; null when unknown. Uses UTC noon anchor. */
export function daysUntilDue(dateStr) {
  const due = parseDueDate(dateStr)
  if (!due) return null
  const today = new Date()
  today.setUTCHours(12, 0, 0, 0)
  return Math.round((due.getTime() - today.getTime()) / 86400000)
}

/** Bucket key for KEV due-date histograms (matches feed/Morning Brief windows). */
export function kevDueBucket(days) {
  if (days == null) return '31+'
  if (days < 0) return 'overdue'
  if (days <= 7) return '0-7'
  if (days <= 14) return '8-14'
  if (days <= 30) return '15-30'
  return '31+'
}

/** Full-saturation red only for overdue / due today / due tomorrow. */
export function kevDueIsImmediate(days) {
  return days !== null && days <= 1
}

/** Left accent bar on CVE cards and sidebar KEV rows. */
export function kevAccentBarClass(days) {
  if (days === null) return 'accent-neutral'
  if (days < 0 || days <= 1) return 'accent-urgent'
  if (days <= 7) return 'accent-red-dim'
  if (days <= 14) return 'accent-amber-dim'
  return 'accent-neutral'
}

/** Card/sidebar chip class — immediate urgency uses full red; metadata stays dim. */
export function kevDueUrgencyClass(days) {
  if (days === null) return 'badge-neutral'
  if (days < 0) return 'badge-overdue'
  if (days <= 1) return 'badge-urgent'
  if (days < 7) return 'badge-urgent-dim'
  if (days < 14) return 'badge-soon'
  return 'badge-neutral'
}

/** Human-readable KEV due date for display (UTC — matches CISA catalogue dates). */
export function formatKevDueDate(dateStr) {
  if (!dateStr) return null
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    })
  } catch {
    return String(dateStr).slice(0, 10)
  }
}

/** Analyst-facing label for KEV remediation countdown. */
export function kevDueLabel(days) {
  if (days === null) return null
  if (days < 0) return 'Overdue'
  if (days === 0) return 'Due today'
  if (days === 1) return 'Due in 1 day'
  return `Due in ${days} days`
}

/** Inclusive UTC due-date range for a KEV histogram bucket (for onBucketClick). */
export function kevBucketDateRange(bucketKey) {
  const today = new Date()
  today.setUTCHours(12, 0, 0, 0)
  const fmt = (d) => {
    const x = new Date(d)
    return x.toISOString().slice(0, 10)
  }
  const addDays = (n) => {
    const d = new Date(today)
    d.setUTCDate(d.getUTCDate() + n)
    return fmt(d)
  }
  const todayStr = fmt(today)

  switch (bucketKey) {
    case 'overdue':
      return { bucket: bucketKey, start: null, end: addDays(-1) }
    case '0-7':
      return { bucket: bucketKey, start: todayStr, end: addDays(7) }
    case '8-14':
      return { bucket: bucketKey, start: addDays(8), end: addDays(14) }
    case '15-30':
      return { bucket: bucketKey, start: addDays(15), end: addDays(30) }
    case '31+':
      return { bucket: bucketKey, start: addDays(31), end: null }
    default:
      return { bucket: bucketKey, start: null, end: null }
  }
}

/** Client-side due-date filter for action_queue rows (histogram bucket / due window). */
export function kevDueDateInWindow(dueDateStr, window) {
  if (!window) return true
  if (!dueDateStr) return false
  const dueStr = String(dueDateStr).slice(0, 10)
  if (window.start && dueStr < window.start) return false
  if (window.end && dueStr > window.end) return false
  return true
}

/** Human label for an active KEV histogram bucket filter. */
export function kevBucketFilterLabel(bucketKey) {
  switch (bucketKey) {
    case 'overdue': return 'Overdue'
    case '0-7': return '0–7d'
    case '8-14': return '8–14d'
    case '15-30': return '15–30d'
    case '31+': return '31d+'
    default: return bucketKey
  }
}
