import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import './LoginPage.css'

export default function LoginPage() {
  const { status, login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [shake, setShake] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authed') {
    const from = location.state?.from?.pathname || '/'
    return <Navigate to={from} replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    setError('')
    try {
      await login(email, password, rememberMe)
      const from = location.state?.from?.pathname || '/'
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed')
      setShake(true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-bg" aria-hidden="true" />
      <div
        className={`login-card${shake ? ' login-shake' : ''}`}
        onAnimationEnd={() => setShake(false)}
      >
        <div className="login-brand">
          <span className="login-wordmark">BRIEFR</span>
          <span className="login-tagline mono">CVE intelligence</span>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-field">
            <span className="login-label mono">Email</span>
            <input
              type="email"
              className="login-input"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
              required
            />
          </label>

          <label className="login-field">
            <span className="login-label mono">Password</span>
            <div className="login-password-wrap">
              <input
                type={showPassword ? 'text' : 'password'}
                className="login-input"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="login-password-toggle"
                onClick={() => setShowPassword(v => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>

          <label className="login-remember mono">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={e => setRememberMe(e.target.checked)}
            />
            <span>
              Remember me
              <span className="login-remember-hint">
                {' '}— stay signed in on this device for 30 days. Leave
                unchecked on a shared machine.
              </span>
            </span>
          </label>

          {error && <div className="login-error mono">{error}</div>}

          <button type="submit" className="login-submit" disabled={submitting}>
            {submitting ? (
              <span className="login-dots" aria-label="Signing in">
                <span /><span /><span />
              </span>
            ) : (
              'Sign in'
            )}
          </button>
        </form>

        <div className="login-footer mono">
          <a href="/privacy">Privacy Policy</a>
          <span className="login-footer-sep" aria-hidden="true">&middot;</span>
          <a href="/terms">Terms of Use</a>
        </div>
      </div>
    </div>
  )
}
