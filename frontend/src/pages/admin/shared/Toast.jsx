import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, XCircle, AlertTriangle, Info, X, Copy } from 'lucide-react'

const VARIANT_ICON = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const DEFAULT_DURATION = {
  success: 4500,
  error: 10000,
  warning: 8000,
  info: 4500,
}

function normalizeToast(input, ok = true) {
  if (typeof input === 'string') {
    return {
      message: input,
      variant: ok ? 'success' : 'error',
      actions: [],
      requestId: null,
      duration: ok ? DEFAULT_DURATION.success : DEFAULT_DURATION.error,
    }
  }
  return {
    message: input.message || '',
    variant: input.variant || 'info',
    actions: input.actions || [],
    requestId: input.requestId || null,
    duration: input.duration ?? DEFAULT_DURATION[input.variant] ?? DEFAULT_DURATION.info,
  }
}

export function useToast() {
  const [toasts, setToasts] = useState([])
  const dismiss = useCallback((id) => {
    setToasts(t => t.map(x => (x.id === id ? { ...x, leaving: true } : x)))
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 180)
  }, [])
  const show = useCallback((msgOrOpts, ok = true) => {
    const id = Date.now() + Math.random()
    const payload = normalizeToast(msgOrOpts, ok)
    setToasts(t => [...t, { id, ...payload, leaving: false }])
    if (payload.variant !== 'error') {
      setTimeout(() => dismiss(id), payload.duration)
    }
  }, [dismiss])
  return { toasts, show, dismiss }
}

function copyRequestId(requestId) {
  if (!requestId || !navigator.clipboard?.writeText) return
  navigator.clipboard.writeText(requestId).catch(() => {})
}

export function ToastArea({ toasts, onDismiss }) {
  return (
    <div className="admin-toast-area">
      {toasts.map(t => {
        const Icon = VARIANT_ICON[t.variant] || Info
        const variantClass = t.variant === 'success'
          ? 'admin-toast-ok'
          : t.variant === 'error'
            ? 'admin-toast-error'
            : t.variant === 'warning'
              ? 'admin-toast-warn'
              : 'admin-toast-info'
        return (
          <div
            key={t.id}
            className={`admin-toast ${variantClass} ${t.leaving ? 'admin-toast-leaving' : ''}`}
            role={t.variant === 'error' ? 'alert' : 'status'}
          >
            <Icon size={15} strokeWidth={2} />
            <div className="admin-toast-body">
              <span className="admin-toast-msg">{t.message}</span>
              {t.requestId && (
                <div className="admin-toast-request">
                  <span className="mono">ID {t.requestId}</span>
                  <button
                    type="button"
                    className="admin-toast-copy"
                    onClick={() => copyRequestId(t.requestId)}
                    title="Copy request ID"
                  >
                    <Copy size={12} strokeWidth={2} />
                  </button>
                </div>
              )}
              {t.actions?.length > 0 && (
                <div className="admin-toast-actions">
                  {t.actions.map(action => (
                    <Link
                      key={action.href}
                      to={action.href}
                      className="admin-toast-action"
                      onClick={() => onDismiss?.(t.id)}
                    >
                      {action.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
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
