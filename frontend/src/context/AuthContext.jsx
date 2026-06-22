import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  fetchMe,
  fetchSetupRequired,
  login as apiLogin,
  logout as apiLogout,
  setupAccount,
} from '../api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading')
  const [setupRequired, setSetupRequired] = useState(false)

  const refreshAuthState = useCallback(async () => {
    try {
      const me = await fetchMe()
      setUser(me)
      setStatus('authed')
      return me
    } catch {
      setUser(null)
      setStatus('anon')
      return null
    }
  }, [])

  useEffect(() => {
    refreshAuthState()
    fetchSetupRequired()
      .then(({ required }) => setSetupRequired(required))
      .catch(() => setSetupRequired(false))
  }, [refreshAuthState])

  useEffect(() => {
    const handleExpired = () => {
      setUser(null)
      setStatus('anon')
    }
    window.addEventListener('briefr-auth-expired', handleExpired)
    return () => window.removeEventListener('briefr-auth-expired', handleExpired)
  }, [])

  const login = useCallback(async (username, password, rememberMe = false) => {
    const me = await apiLogin(username, password, rememberMe)
    setUser(me)
    setStatus('authed')
    return me
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setUser(null)
      setStatus('anon')
    }
  }, [])

  const completeSetup = useCallback(async (username, password) => {
    const me = await setupAccount(username, password)
    setUser(me)
    setStatus('authed')
    setSetupRequired(false)
    return me
  }, [])

  const value = useMemo(
    () => ({ user, status, setupRequired, login, logout, completeSetup, refreshAuthState }),
    [user, status, setupRequired, login, logout, completeSetup, refreshAuthState],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
