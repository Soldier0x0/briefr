import { useState, useEffect } from 'react'
import { Monitor, Smartphone, Globe } from 'lucide-react'
import { fetchSessions, revokeSession } from '../../api.js'

function uaIcon(ua = '') {
  const s = ua.toLowerCase()
  if (s.includes('mobile') || s.includes('android') || s.includes('iphone')) return <Smartphone size={13} />
  if (s.includes('mozilla') || s.includes('chrome') || s.includes('safari')) return <Monitor size={13} />
  return <Globe size={13} />
}

function uaShort(ua = '') {
  if (!ua) return '—'
  const m = ua.match(/(Chrome|Firefox|Safari|Edge|Opera)[\/ ]([\d.]+)/) || ua.match(/(curl|python|go-http)/)
  return m ? `${m[1]} ${m[2] || ''}`.trim() : ua.slice(0, 40)
}

function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function SessionsPage({ toast }) {
  const [data, setData] = useState(null)
  const [revoking, setRevoking] = useState(null)

  async function load() {
    try { setData(await fetchSessions()) } catch (e) { toast(e.message, false) }
  }

  useEffect(() => { load() }, [])

  async function handleRevoke(id) {
    setRevoking(id)
    try {
      await revokeSession(id)
      toast('Session revoked', true)
      await load()
    } catch (e) {
      toast(e.message, false)
    } finally {
      setRevoking(null)
    }
  }

  const user = data?.user
  const sessions = data?.sessions ?? []

  return (
    <div>
      <h1 className="admin-page-title">Login &amp; sessions</h1>
      <p className="admin-page-subtitle">Your account details and active login sessions.</p>

      {user && (
        <div className="admin-card" style={{ marginBottom: '1.25rem' }}>
          <div className="admin-card-title">Account</div>
          <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--fg3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Username</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{user.username}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--fg3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Role</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{user.role}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--fg3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Last login</div>
              <div style={{ fontSize: '0.9rem' }}>{fmtDate(user.last_login_at)}</div>
            </div>
          </div>
        </div>
      )}

      <div className="admin-card">
        <div className="admin-card-title">Active sessions ({sessions.length})</div>
        {sessions.length === 0 ? (
          <p style={{ color: 'var(--fg3)', fontSize: '0.85rem', margin: '0.5rem 0 0' }}>No active sessions found.</p>
        ) : (
          <div style={{ overflowX: 'auto', marginTop: '0.5rem' }}>
            <table className="admin-table" style={{ minWidth: '600px' }}>
              <thead>
                <tr>
                  <th>Client</th>
                  <th>IP</th>
                  <th>Created</th>
                  <th>Last used</th>
                  <th>Expires</th>
                  <th>Remember me</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} style={s.is_current ? { background: 'var(--bg3)' } : {}}>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--fg2)' }}>
                        {uaIcon(s.user_agent)}
                        <span style={{ fontSize: '0.8rem' }}>{uaShort(s.user_agent)}</span>
                        {s.is_current && <span className="admin-badge admin-badge-green" style={{ fontSize: '0.65rem' }}>current</span>}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>{s.ip || '—'}</td>
                    <td style={{ fontSize: '0.8rem' }}>{fmtDate(s.created_at)}</td>
                    <td style={{ fontSize: '0.8rem' }}>{fmtDate(s.last_used_at)}</td>
                    <td style={{ fontSize: '0.8rem' }}>{fmtDate(s.expires_at)}</td>
                    <td>
                      {s.remember_me
                        ? <span className="admin-badge admin-badge-green">yes</span>
                        : <span className="admin-badge" style={{ color: 'var(--fg3)' }}>no</span>}
                    </td>
                    <td>
                      <button
                        className="admin-btn admin-btn-danger admin-btn-sm"
                        disabled={s.is_current || revoking === s.id}
                        onClick={() => handleRevoke(s.id)}
                        title={s.is_current ? 'Cannot revoke your current session' : 'Revoke this session'}
                      >
                        {revoking === s.id ? 'Revoking…' : 'Revoke'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
