import { useState, useEffect, useRef, useMemo } from 'react'
import useModalLayer from '../hooks/useModalLayer.js'
import './CommandPalette.css'

export default function CommandPalette({ open, onClose, getCommands }) {
  const [query, setQuery] = useState('')
  const [highlight, setHighlight] = useState(0)
  const panelRef = useRef(null)

  useModalLayer(open, panelRef, { trackDepth: true, trapFocus: true })

  useEffect(() => {
    if (!open) {
      setQuery('')
      setHighlight(0)
    }
  }, [open])

  const commands = useMemo(() => getCommands(query), [getCommands, query])

  useEffect(() => {
    setHighlight(0)
  }, [query, commands.length])

  function runCommand(cmd) {
    onClose()
    cmd.run()
  }

  function handleKeyDown(e) {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight(i => Math.min(i + 1, Math.max(0, commands.length - 1)))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight(i => Math.max(i - 1, 0))
      return
    }
    if (e.key === 'Enter' && commands[highlight]) {
      e.preventDefault()
      runCommand(commands[highlight])
    }
  }

  if (!open) return null

  return (
    <div
      className="cmdk-overlay"
      onClick={e => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="cmdk-panel"
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <input
          type="search"
          className="cmdk-input mono"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Tab, CVE-2024-1234, IOC value, refresh…"
          aria-label="Command search"
          autoComplete="off"
          autoFocus
        />
        <ul className="cmdk-list" role="listbox" aria-label="Commands">
          {commands.map((cmd, idx) => (
            <li key={cmd.id} role="presentation">
              <button
                type="button"
                className={`cmdk-item${idx === highlight ? ' cmdk-item--active' : ''}`}
                role="option"
                aria-selected={idx === highlight}
                onMouseEnter={() => setHighlight(idx)}
                onClick={() => runCommand(cmd)}
              >
                <span className="cmdk-label">{cmd.label}</span>
                {cmd.hint && <span className="cmdk-hint mono">{cmd.hint}</span>}
              </button>
            </li>
          ))}
        </ul>
        {commands.length === 0 && (
          <p className="cmdk-empty mono">No matching commands.</p>
        )}
      </div>
    </div>
  )
}
