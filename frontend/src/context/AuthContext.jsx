import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { fetchMe, login as apiLogin, logout as apiLogout } from '../api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading')

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
  }, [refreshAuthState])

  useEffect(() => {
    const handleExpired = () => {
      setUser(null)
      setStatus('anon')
    }
    window.addEventListener('briefr-auth-expired', handleExpired)
    return () => window.removeEventListener('briefr-auth-expired', handleExpired)
  }, [])

  const login = useCallback(async (email, password, rememberMe = false) => {
    const me = await apiLogin(email, password, rememberMe)
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

  const value = useMemo(
    () => ({ user, status, login, logout, refreshAuthState }),
    [user, status, login, logout, refreshAuthState],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
