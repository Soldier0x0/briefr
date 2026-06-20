import { COMING_SOON_INFO } from './constants.js'

export default function ComingSoonPage({ pageId, setPage }) {
  const info = COMING_SOON_INFO[pageId] || { title: 'Coming soon', message: 'This feature is under development.' }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4rem 2rem', textAlign: 'center' }}>
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔒</div>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.75rem' }}>{info.title}</h2>
      <p style={{ fontSize: '0.9rem', color: 'var(--text2)', maxWidth: 480, lineHeight: 1.6, marginBottom: '1.5rem' }}>{info.message}</p>
      <button className="admin-btn admin-btn-ghost" onClick={() => setPage('overview')}>← Back to System health</button>
    </div>
  )
}
