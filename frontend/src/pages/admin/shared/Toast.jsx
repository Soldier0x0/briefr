import { useState, useCallback } from 'react'

export function useToast() {
  const [toasts, setToasts] = useState([])
  const show = useCallback((msg, ok = true) => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, ok }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500)
  }, [])
  return { toasts, show }
}

export function ToastArea({ toasts }) {
  return (
    <div className="admin-toast-area">
      {toasts.map(t => (
        <div key={t.id} className={`admin-toast ${t.ok ? 'admin-toast-ok' : 'admin-toast-error'}`}>
          {t.msg}
        </div>
      ))}
    </div>
  )
}
