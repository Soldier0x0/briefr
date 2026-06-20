import { useEffect, useRef, useState } from 'react'

export default function AdminPage_KeyModal({ onSubmit, error }) {
  const [key, setKey] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  function handleSubmit(e) {
    e.preventDefault()
    if (key.trim()) onSubmit(key.trim())
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '2rem',
        minWidth: '340px',
        maxWidth: '420px',
        width: '100%',
        boxShadow: 'var(--shadow-card)',
      }}>
        <h2 style={{ margin: '0 0 0.5rem', color: 'var(--text-primary)', fontSize: '1.125rem' }}>
          Admin Authentication
        </h2>
        <p style={{ margin: '0 0 1.25rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Enter your admin API key to access the dashboard.
        </p>
        {error && (
          <div style={{
            background: 'rgba(232, 85, 51, 0.1)',
            border: '1px solid var(--color-critical)',
            borderRadius: '4px',
            padding: '0.5rem 0.75rem',
            marginBottom: '1rem',
            color: 'var(--color-critical)',
            fontSize: '0.8125rem',
          }}>
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="password"
            value={key}
            onChange={e => setKey(e.target.value)}
            placeholder="Admin API Key"
            style={{
              display: 'block',
              width: '100%',
              boxSizing: 'border-box',
              padding: '0.5rem 0.75rem',
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              borderRadius: '4px',
              color: 'var(--text-primary)',
              fontSize: '0.9375rem',
              marginBottom: '1rem',
              outline: 'none',
            }}
            onKeyDown={e => { if (e.key === 'Enter') handleSubmit(e) }}
          />
          <button
            type="submit"
            disabled={!key.trim()}
            style={{
              width: '100%',
              padding: '0.5rem',
              background: '#e85533',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              fontSize: '0.9375rem',
              cursor: key.trim() ? 'pointer' : 'not-allowed',
              opacity: key.trim() ? 1 : 0.6,
            }}
          >
            Authenticate
          </button>
        </form>
      </div>
    </div>
  )
}
