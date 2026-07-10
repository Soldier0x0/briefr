import { useState } from 'react'

// Single guarded entry point for destructive bulk-clear actions: pick a
// target from a dropdown, then type "clear" (case-insensitive) to enable
// the button. Replaces scattered per-section Purge/Clear All buttons that
// fire on a single click.
export default function GuardedPurgePanel({ targets }) {
  const [selected, setSelected] = useState(targets[0]?.target ?? '')
  const [confirmText, setConfirmText] = useState('')
  const [daysBack, setDaysBack] = useState('')
  const target = targets.find(t => t.target === selected)
  const destructive = !!target?.confirmWord
  const matched = confirmText.trim().toLowerCase() === 'clear'

  function selectTarget(t) {
    setSelected(t)
    setConfirmText('')
    setDaysBack('')
  }

  function run() {
    if (destructive && !matched) return
    target.run(target.extraDaysBack ? daysBack : undefined)
    setConfirmText('')
  }

  if (!target) return null

  return (
    <div className="purge-panel purge-panel--compact">
      <select className="admin-select" value={selected} onChange={e => selectTarget(e.target.value)}>
        {targets.map(t => <option key={t.target} value={t.target}>{t.title}</option>)}
      </select>

      <div className="purge-card" style={{ marginTop: '0.5rem' }}>
        <div className="purge-card-desc">{target.desc}</div>
        <div className="purge-card-impact">Impact: {target.impact}</div>

        {target.extraDaysBack && (
          <input
            className="admin-input"
            type="number"
            min="1"
            placeholder="Days back (optional)"
            value={daysBack}
            onChange={e => setDaysBack(e.target.value)}
            style={{ marginTop: '0.5rem', maxWidth: 160 }}
          />
        )}

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.5rem', flexWrap: 'wrap' }}>
          {destructive && (
            <input
              className="admin-input"
              placeholder='Type "clear" to enable'
              value={confirmText}
              onChange={e => setConfirmText(e.target.value)}
              style={{ maxWidth: 200 }}
            />
          )}
          <button
            className="admin-btn admin-btn-danger"
            disabled={destructive && !matched}
            onClick={run}
          >
            {target.actionLabel || 'Clear'}
          </button>
        </div>
      </div>
    </div>
  )
}
