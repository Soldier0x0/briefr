import { useState, useEffect, useRef } from 'react'
import useModalLayer from '../hooks/useModalLayer.js'
import './ShortcutsPanel.css'

const SHORTCUTS = [
  { key: '/',     desc: 'Focus search' },
  { key: 'F',     desc: 'Cycle filters' },
  { key: 'Esc',   desc: 'Close drawer or modal' },
  { key: '↑ ↓',   desc: 'Navigate CVE cards' },
  { key: 'Enter', desc: 'Open selected card' },
  { key: 'G D',   desc: 'Generate digest' },
  { key: 'C',     desc: 'Copy report (drawer open)' },
]

export default function ShortcutsPanel({ placement = 'header' }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

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
      {open && (
        <div
          className="shortcuts-panel"
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
        </div>
      )}
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
