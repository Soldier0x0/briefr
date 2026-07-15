import { useState, useEffect, useRef } from 'react'
import useModalLayer from '../hooks/useModalLayer.js'
import './ShortcutsPanel.css'

const SHORTCUTS = [
  { key: '⌘K',    desc: 'Command palette (works while typing)' },
  { key: '/',     desc: 'Focus feed search (when search is not focused)' },
  { key: 'F',     desc: 'Cycle feed filters (not while typing)' },
  { key: 'Esc',   desc: 'Close drawer or modal' },
  { key: '↑ ↓',   desc: 'Navigate CVE cards (feed, search unfocused)' },
  { key: 'Enter', desc: 'Open selected card' },
  { key: 'G then D', desc: 'Generate digest (feed only, not while typing)' },
  { key: 'C',     desc: 'Copy report (drawer open, not while typing)' },
]

export default function ShortcutsPanel({ placement = 'header', listOnly = false, onClose }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

  const panel = (
    <div
      className={`shortcuts-panel${listOnly ? ' shortcuts-panel--inline' : ''}`}
      role="dialog"
      aria-label="Keyboard shortcuts reference"
    >
      <div className="shortcuts-title mono">// SHORTCUTS</div>
      <ul className="shortcuts-list">
        {SHORTCUTS.map(s => (
          <li key={s.key} className="shortcut-row">
            <span className="shortcut-key mono" aria-label={`Key: ${s.key}`}>
              {s.key}
            </span>
            <span className="shortcut-desc">{s.desc}</span>
          </li>
        ))}
      </ul>
      {listOnly && onClose && (
        <button type="button" className="shortcuts-back-btn mono" onClick={onClose}>
          Back
        </button>
      )}
    </div>
  )

  if (listOnly) {
    return panel
  }

  // Owns its Escape — register depth so the global handler stands down while
  // the panel is open (popover, so no focus trap).
  useModalLayer(open, wrapRef, { trackDepth: true, trapFocus: false })

  useEffect(() => {
    if (!open) return
    function onDown(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className={`shortcuts-wrap shortcuts-wrap--${placement}`} ref={wrapRef}>
      {open && panel}
      <button
        className="shortcuts-btn"
        onClick={() => setOpen(v => !v)}
        aria-label="Toggle keyboard shortcuts help"
        aria-expanded={open}
        title="Keyboard shortcuts"
      >
        {placement === 'header' ? 'KEYS' : '?'}
      </button>
    </div>
  )
}
