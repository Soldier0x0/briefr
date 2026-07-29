import { useCallback, useState } from 'react'
import { copyToClipboard } from '../utils/report.js'
import { notifyCopyFailure, notifyCopySuccess } from './Toast.jsx'
import './CodePanel.css'

/**
 * Geist-inspired code panel — matches the BRIEFR docs portal fenced-block design.
 * Copy-friendly: full-width pre, user-select all, header strip with copy action.
 */
export default function CodePanel({
  code,
  title,
  language = 'yaml',
  copyLabel = 'Copy',
  className = '',
  maxHeight = 360,
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async (e) => {
    e?.stopPropagation?.()
    const ok = await copyToClipboard(code)
    if (ok) {
      setCopied(true)
      notifyCopySuccess('Copied to clipboard')
      setTimeout(() => setCopied(false), 1500)
    } else {
      notifyCopyFailure()
    }
  }, [code])

  if (!code) return null

  const rootClass = ['code-panel', className].filter(Boolean).join(' ')

  return (
    <div className={rootClass}>
      <div className="code-panel-header">
        {title ? (
          <span className="code-panel-title mono">{title}</span>
        ) : (
          <span className="code-panel-title mono">{language}</span>
        )}
        <button
          type="button"
          className="code-panel-copy mono"
          onClick={handleCopy}
          aria-label={copied ? 'Copied' : copyLabel}
        >
          {copied ? 'Copied!' : copyLabel}
        </button>
      </div>
      <pre
        className="code-panel-body mono"
        style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}
      >
        {code}
      </pre>
    </div>
  )
}
