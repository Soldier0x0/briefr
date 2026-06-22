import { useState, useCallback } from 'react'
import { CheckCircle2, XCircle, X } from 'lucide-react'

export function useToast() {
  const [toasts, setToasts] = useState([])
  const dismiss = useCallback((id) => {
    setToasts(t => t.map(x => (x.id === id ? { ...x, leaving: true } : x)))
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 180)
  }, [])
  const show = useCallback((msg, ok = true) => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, ok }])
    setTimeout(() => dismiss(id), 3500)
  }, [dismiss])
  return { toasts, show, dismiss }
}

export function ToastArea({ toasts, onDismiss }) {
  return (
    <div className="admin-toast-area">
      {toasts.map(t => {
        const Icon = t.ok ? CheckCircle2 : XCircle
        return (
          <div
            key={t.id}
            className={`admin-toast ${t.ok ? 'admin-toast-ok' : 'admin-toast-error'} ${t.leaving ? 'admin-toast-leaving' : ''}`}
          >
            <Icon size={15} strokeWidth={2} />
            <span className="admin-toast-msg">{t.msg}</span>
            {onDismiss && (
              <button className="admin-toast-close" onClick={() => onDismiss(t.id)} aria-label="Dismiss notification">
                <X size={13} strokeWidth={2} />
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
