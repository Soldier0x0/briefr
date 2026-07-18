import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../../api.js'

/**
 * Embeddings E5 — Admin search service tokens (show-once plaintext on create).
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
      setTokens(res?.data || [])
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
      toast?.success?.('Search token created — copy it now; it will not be shown again')
      await load()
    } catch (err) {
      toast?.error?.(err?.message || 'Create failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleRevoke(id) {
    if (!window.confirm(`Revoke search token #${id}?`)) return
    setBusy(true)
    try {
      await adminApi.delJson(`/search-tokens/${id}`)
      toast?.success?.('Token revoked')
      await load()
    } catch (err) {
      toast?.error?.(err?.message || 'Revoke failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="admin-panel" aria-labelledby="search-tokens-heading">
      <h3 id="search-tokens-heading" className="mono">
        Search API tokens
      </h3>
      <p className="admin-muted mono" style={{ marginBottom: 'var(--space-3)' }}>
        Scoped Bearer tokens (<code>briefr_search_…</code>) for hybrid search, related CVEs, and
        CVE detail. Hash stored with bcrypt; plaintext shown once at create.
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
              toast?.success?.('Copied')
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
      {tokens.length > 0 && (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Prefix</th>
              <th>Status</th>
              <th>Created</th>
              <th>Last used</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {tokens.map((t) => (
              <tr key={t.id}>
                <td className="mono">{t.name}</td>
                <td className="mono">{t.token_prefix}…</td>
                <td className="mono">{t.active ? 'active' : 'revoked'}</td>
                <td className="mono">{t.created_at || '—'}</td>
                <td className="mono">{t.last_used_at || '—'}</td>
                <td>
                  {t.active && (
                    <button
                      type="button"
                      className="admin-btn admin-btn-danger"
                      disabled={busy}
                      onClick={() => handleRevoke(t.id)}
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
