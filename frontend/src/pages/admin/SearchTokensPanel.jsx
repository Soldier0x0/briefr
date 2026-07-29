import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../../api.js'

function notifyToast(toast, message, ok) {
  if (typeof toast === 'function') {
    toast(message, ok)
    return
  }
  if (ok) toast?.success?.(message)
  else toast?.error?.(message)
}

/**
 * Optional programmatic search access tokens (show-once plaintext on create).
 */
export default function SearchTokensPanel({ toast }) {
  const [tokens, setTokens] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [onceToken, setOnceToken] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await adminApi.get('/search-tokens')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const rows = Array.isArray(data) ? data : (data?.tokens || [])
      setTokens(rows)
    } catch (e) {
      setError(e?.message || 'Failed to load search tokens')
      setTokens([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleCreate(e) {
    e.preventDefault()
    setBusy(true)
    setOnceToken(null)
    try {
      const created = await adminApi.postJson('/search-tokens', {
        name: name.trim() || 'Search token',
      })
      setOnceToken(created?.token || null)
      setName('')
      notifyToast(toast, 'Search token created — copy it now; it will not be shown again', true)
      await load()
    } catch (err) {
      notifyToast(toast, err?.message || 'Create failed', false)
    } finally {
      setBusy(false)
    }
  }

  async function handleRevoke(id) {
    if (!window.confirm(`Revoke search token #${id}?`)) return
    setBusy(true)
    try {
      await adminApi.delJson(`/search-tokens/${id}`)
      notifyToast(toast, 'Token revoked', true)
      await load()
    } catch (err) {
      notifyToast(toast, err?.message || 'Revoke failed', false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="admin-panel" aria-labelledby="search-tokens-heading">
      <h3 id="search-tokens-heading" className="admin-section-title">
        Programmatic search access
      </h3>
      <p className="admin-section-desc">
        Optional Bearer tokens for automation (hybrid search, related CVEs, CVE detail API).
        Only needed if you integrate BRIEFR search into another tool — not required for normal use.
      </p>

      <form className="admin-inline-form" onSubmit={handleCreate}>
        <input
          className="admin-input"
          value={name}
          onChange={(ev) => setName(ev.target.value)}
          placeholder="Token label"
          maxLength={120}
          aria-label="Search token name"
          disabled={busy}
        />
        <button type="submit" className="admin-btn" disabled={busy}>
          Create token
        </button>
      </form>

      {onceToken && (
        <div className="admin-callout" role="status">
          <div className="mono" style={{ marginBottom: 'var(--space-2)' }}>
            Copy now — will not be shown again
          </div>
          <code className="mono" style={{ wordBreak: 'break-all' }}>
            {onceToken}
          </code>
          <button
            type="button"
            className="admin-btn"
            style={{ marginTop: 'var(--space-2)' }}
            onClick={() => {
              navigator.clipboard?.writeText(onceToken)
              notifyToast(toast, 'Copied', true)
            }}
          >
            Copy
          </button>
        </div>
      )}

      {loading && <p className="mono admin-muted">Loading…</p>}
      {error && (
        <p className="mono" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && tokens.length === 0 && (
        <p className="mono admin-muted">No search tokens yet.</p>
      )}
      {!loading && !error && tokens.length > 0 && (
        <table className="metering-table" style={{ marginTop: 'var(--space-3)' }}>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Created</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tokens.map((t) => (
              <tr key={t.id}>
                <td className="admin-config-value mono">{t.name || `Token #${t.id}`}</td>
                <td className="mono">{t.created_at ? String(t.created_at).slice(0, 19) : '—'}</td>
                <td>
                  <button
                    type="button"
                    className="admin-btn admin-btn-ghost"
                    disabled={busy}
                    onClick={() => handleRevoke(t.id)}
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
