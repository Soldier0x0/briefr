import { useEffect, useState } from 'react'
import { adminApi } from '../../../api.js'
import { ConfirmModal as UiConfirmModal } from '../../../components/ui/index.js'

// Generic confirm-text gate, standardized across all destructive admin actions.
// Pass explicit title/message/confirmWord for one-off cases, or actionId to pull
// the confirm word + description from GET /api/admin/destructive-actions.
export default function ConfirmModal({ actionId, title, message, confirmWord, onConfirm, onCancel }) {
  const [apiAction, setApiAction] = useState(null)

  useEffect(() => {
    if (!actionId) return undefined
    adminApi.get('/destructive-actions').then(r => r.json()).then(list => {
      const found = (list || []).find(a => a.id === actionId)
      if (found) setApiAction(found)
    }).catch(() => {})
    return undefined
  }, [actionId])

  const displayTitle = title ?? apiAction?.description ?? ''
  const displayMessage = message ?? apiAction?.description ?? ''
  const word = confirmWord ?? apiAction?.confirm_word ?? ''

  return (
    <UiConfirmModal
      title={displayTitle}
      message={displayMessage}
      confirmWord={word}
      onConfirm={onConfirm}
      onCancel={onCancel}
      className="admin-modal"
      overlayClassName="admin-modal-overlay"
    />
  )
}
