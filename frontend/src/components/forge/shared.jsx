import { useCallback, useState } from 'react'

export const STATUS_LABELS = {
  yours: 'YOURS',
  community: 'COMMUNITY',
  gap: 'GAP',
}

export function StatusChip({ status }) {
  return (
    <span className={`fg-status-chip fg-status-${status} mono`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

export function CopyButton({ text, label = 'COPY' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    if (!navigator.clipboard?.writeText) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {})
  }, [text])

  return (
    <button type="button" className="fg-copy-btn mono" onClick={handleCopy}>
      {copied ? 'COPIED ✓' : label}
    </button>
  )
}

export function SkeletonRows({ count = 8 }) {
  return (
    <ul className="fg-skeleton-list" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="fg-skeleton-row" />
      ))}
    </ul>
  )
}
