import { useState, useEffect } from 'react'
import { adminApi } from '../../../api.js'

// Generic confirm-text gate, standardized across all destructive admin actions.
// Pass explicit title/message/confirmWord for one-off cases, or actionId to pull
// the confirm word + description from GET /api/admin/destructive-actions.
export default function ConfirmModal({ actionId, title, message, confirmWord, onConfirm, onCancel }) {
  const [input, setInput] = useState('')
  const [apiAction, setApiAction] = useState(null)

  useEffect(() => {
    if (!actionId) return
    adminApi.get('/destructive-actions').then(r => r.json()).then(list => {
      const found = (list || []).find(a => a.id === actionId)
      if (found) setApiAction(found)
    }).catch(() => {})
  }, [actionId])

  const displayTitle = title ?? apiAction?.description ?? ''
  const displayMessage = message ?? apiAction?.description ?? ''
  const word = confirmWord ?? apiAction?.confirm_word ?? ''
  return (
    <div className="admin-modal-overlay">
      <div className="admin-modal">
        <div className="admin-modal-title">{displayTitle}</div>
        <div className="admin-modal-body">{displayMessage}</div>
        {word && (
          <div style={{ marginTop: '1rem' }}>
            <label style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.4rem', display: 'block' }}>
              Type <code className="mono">{word}</code> to confirm
            </label>
            <input
              className="admin-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={word}
              autoFocus
            />
          </div>
        )}
        <div className="admin-modal-actions">
          <button className="admin-btn admin-btn-ghost" onClick={onCancel}>Cancel</button>
          <button
            className="admin-btn admin-btn-danger"
            onClick={() => onConfirm(input)}
            disabled={word ? input !== word : false}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
