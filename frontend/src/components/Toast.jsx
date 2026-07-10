import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, XCircle, AlertTriangle, Info, X, Copy } from 'lucide-react'

const ToastContext = createContext(null)

const VARIANT_ICON = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const DEFAULT_DURATION = {
  success: 8000,
  error: null,
  warning: null,
  info: 8000,
}

const HOVER_RESUME_GRACE_MS = 400
const DEDUPE_WINDOW_MS = 2000
const MAX_VISIBLE = 4

function normalizeToast(input, ok = true) {
  if (typeof input === 'string') {
    const variant = ok ? 'success' : 'error'
    return {
      message: input,
      variant,
      actions: [],
      requestId: null,
      duration: DEFAULT_DURATION[variant],
    }
  }
  const variant = input.variant || 'info'
  return {
    message: input.message || '',
    variant,
    actions: input.actions || [],
    requestId: input.requestId || null,
    duration: input.duration !== undefined ? input.duration : DEFAULT_DURATION[variant],
  }
}

const SUPPRESSED_STATUSES = new Set([401, 422])

export function notifyApiError(err) {
  if (SUPPRESSED_STATUSES.has(err?.status)) return
  window.dispatchEvent(new CustomEvent('briefr-api-error', {
    detail: { message: err?.message || 'Request could not be completed', requestId: err?.requestId || '' },
  }))
}

function useToastState() {
  const [toasts, setToasts] = useState([])
  const lastShownRef = useRef({ message: '', variant: '', requestId: null, at: 0 })

  const dismiss = useCallback((id) => {
    setToasts(t => t.map(x => (x.id === id ? { ...x, leaving: true } : x)))
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 180)
  }, [])

  const show = useCallback((msgOrOpts, ok = true) => {
    const payload = normalizeToast(msgOrOpts, ok)
    const now = Date.now()
    if (
      payload.message
      && payload.message === lastShownRef.current.message
      && payload.variant === lastShownRef.current.variant
      && payload.requestId === lastShownRef.current.requestId
      && now - lastShownRef.current.at < DEDUPE_WINDOW_MS
    ) {
      return
    }
    lastShownRef.current = {
      message: payload.message,
      variant: payload.variant,
      requestId: payload.requestId,
      at: now,
    }

    const id = now + Math.random()
    setToasts(t => {
      const next = [...t, { id, ...payload, leaving: false }]
      return next.length > MAX_VISIBLE ? next.slice(-MAX_VISIBLE) : next
    })
  }, [])

  return { toasts, show, dismiss }
}

export function ToastProvider({ children }) {
  const { toasts, show, dismiss } = useToastState()
  const api = useMemo(() => ({ show, dismiss }), [show, dismiss])
  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastArea toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}

const CLIPBOARD_AVAILABLE = typeof navigator !== 'undefined' && Boolean(navigator.clipboard?.writeText)

function ToastItem({ toast, onDismiss }) {
  const Icon = VARIANT_ICON[toast.variant] || Info
  const variantClass = toast.variant === 'success'
    ? 'admin-toast-ok'
    : toast.variant === 'error'
      ? 'admin-toast-error'
      : toast.variant === 'warning'
        ? 'admin-toast-warn'
        : 'admin-toast-info'
  const [copied, setCopied] = useState(false)
  const remainingRef = useRef(toast.duration ?? DEFAULT_DURATION.info ?? 8000)
  const timerRef = useRef(null)
  const pausedRef = useRef(false)
  const deadlineRef = useRef(0)
  const resumeGraceRef = useRef(null)

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  const clearResumeGrace = () => {
    if (resumeGraceRef.current) {
      clearTimeout(resumeGraceRef.current)
      resumeGraceRef.current = null
    }
  }

  const scheduleDismiss = useCallback(() => {
    clearTimer()
    if (toast.duration == null || pausedRef.current) return
    deadlineRef.current = Date.now() + remainingRef.current
    timerRef.current = setTimeout(() => onDismiss(toast.id), remainingRef.current)
  }, [onDismiss, toast.duration, toast.id])

  useEffect(() => {
    if (toast.duration == null) return undefined
    scheduleDismiss()
    return () => {
      clearTimer()
      clearResumeGrace()
    }
  }, [toast.duration, toast.id, scheduleDismiss])

  const pause = () => {
    if (toast.duration == null || pausedRef.current) return
    clearResumeGrace()
    pausedRef.current = true
    remainingRef.current = Math.max(0, deadlineRef.current - Date.now())
    clearTimer()
  }

  const resume = () => {
    if (toast.duration == null || !pausedRef.current) return
    pausedRef.current = false
    clearResumeGrace()
    resumeGraceRef.current = setTimeout(() => {
      resumeGraceRef.current = null
      if (!pausedRef.current) scheduleDismiss()
    }, HOVER_RESUME_GRACE_MS)
  }

  const handleBlur = (e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) resume()
  }

  async function copyRequestId() {
    if (!toast.requestId || !CLIPBOARD_AVAILABLE) return
    try {
      await navigator.clipboard.writeText(toast.requestId)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* ignore */ }
  }

  return (
    <div
      className={`admin-toast ${variantClass} ${toast.leaving ? 'admin-toast-leaving' : ''}`}
      role={toast.variant === 'error' ? 'alert' : 'status'}
      onMouseEnter={pause}
      onMouseLeave={resume}
      onFocus={pause}
      onBlur={handleBlur}
    >
      <Icon size={15} strokeWidth={2} />
      <div className="admin-toast-body">
        <span className="admin-toast-msg">{toast.message}</span>
        {toast.requestId && (
          <div className="admin-toast-request">
            <span className="mono">ref {toast.requestId}</span>
            {CLIPBOARD_AVAILABLE && (
              <button
                type="button"
                className="admin-toast-copy"
                onClick={copyRequestId}
                title="Copy request ID"
              >
                <Copy size={12} strokeWidth={2} />
                {copied ? <span className="admin-toast-copied">Copied</span> : null}
              </button>
            )}
          </div>
        )}
        {toast.actions?.length > 0 && (
          <div className="admin-toast-actions">
            {toast.actions.map(action => (
              <Link
                key={action.href}
                to={action.href}
                className="admin-toast-action"
                onClick={() => onDismiss?.(toast.id)}
              >
                {action.label}
              </Link>
            ))}
          </div>
        )}
      </div>
      {onDismiss && (
        <button className="admin-toast-close" onClick={() => onDismiss(toast.id)} aria-label="Dismiss notification">
          <X size={13} strokeWidth={2} />
        </button>
      )}
    </div>
  )
}

export function ToastArea({ toasts, onDismiss }) {
  return (
    <div className="admin-toast-area" aria-live="polite" aria-relevant="additions">
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  )
}
