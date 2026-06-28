import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { linksForOperation } from '../../../utils/adminLinks.js'

const OperationContext = createContext(null)

function newOpId() {
  return `op-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

export function OperationProvider({ children, toast }) {
  const [operations, setOperations] = useState([])

  const startOperation = useCallback(({ id, label, kind, meta }) => {
    const opId = id || newOpId()
    setOperations(prev => [
      ...prev.filter(o => o.id !== opId),
      {
        id: opId,
        label,
        kind: kind || 'api',
        meta: meta || {},
        status: 'running',
        startedAt: Date.now(),
        stage: null,
      },
    ])
    return opId
  }, [])

  const updateOperation = useCallback((opId, patch) => {
    setOperations(prev => prev.map(o => (o.id === opId ? { ...o, ...patch } : o)))
  }, [])

  const finishOperation = useCallback((opId) => {
    setOperations(prev => prev.filter(o => o.id !== opId))
  }, [])

  const notify = useCallback((payload) => {
    toast?.(payload)
  }, [toast])

  const runAction = useCallback(async ({
    id,
    label,
    kind = 'api',
    meta = {},
    successMessage,
    execute,
  }) => {
    const opId = startOperation({ id, label, kind, meta })
    try {
      const result = await execute()
      finishOperation(opId)
      const requestId = result?.requestId || result?.request_id || null
      const links = linksForOperation(kind, { ...meta, requestId })
      notify({
        message: successMessage || `${label} started`,
        variant: 'success',
        actions: links,
        requestId,
      })
      return result
    } catch (err) {
      finishOperation(opId)
      const requestId = err?.requestId || null
      const links = linksForOperation(kind, { ...meta, requestId, error: true })
      notify({
        message: err?.message || 'Request failed',
        variant: 'error',
        actions: links,
        requestId,
        duration: 10000,
      })
      throw err
    }
  }, [startOperation, finishOperation, notify])

  const value = useMemo(() => ({
    operations,
    startOperation,
    updateOperation,
    finishOperation,
    runAction,
  }), [operations, startOperation, updateOperation, finishOperation, runAction])

  return (
    <OperationContext.Provider value={value}>
      {children}
    </OperationContext.Provider>
  )
}

export function useOperations() {
  const ctx = useContext(OperationContext)
  if (!ctx) {
    throw new Error('useOperations must be used within OperationProvider')
  }
  return ctx
}

export function OperationStrip() {
  const { operations } = useOperations()
  const active = operations.filter(o => o.status === 'running' || o.status === 'pending')
  if (!active.length) return null

  return (
    <div className="admin-operation-strip" role="status" aria-live="polite">
      {active.map(op => {
        const logHref = linksForOperation(op.kind, op.meta)[0]?.href
        return (
          <div key={op.id} className="admin-operation-item">
            <span className="admin-spinner" aria-hidden="true" />
            <span className="admin-operation-label">{op.label}</span>
            {op.stage && <span className="admin-operation-stage">{op.stage}</span>}
            {logHref && (
              <Link to={logHref} className="admin-operation-link">
                View live log
              </Link>
            )}
          </div>
        )
      })}
    </div>
  )
}
