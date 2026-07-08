import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import AssetWarning from '../components/AssetWarning.jsx'
import AssetProfileManage from '../components/AssetProfileManage.jsx'
import AssetWizard from '../components/AssetWizard.jsx'
import SessionLockOverlay from '../components/SessionLockOverlay.jsx'
import SessionIdleWarning from '../components/SessionIdleWarning.jsx'
import { notifyApiError } from '../components/Toast.jsx'
import { fetchCveAssetMatch } from '../api.js'
import { useAuth } from './AuthContext.jsx'
import { useInactivityTimeout } from '../hooks/useInactivityTimeout.js'
import { parseProfileFile, profileToMatchAssets } from '../utils/assetProfileIo.js'
import {
  getRememberProfileOnServer,
  isUserPreferencesLoaded,
  setRememberProfileOnServer,
} from '../utils/userPreferences.js'
import {
  getSavedStackProfile,
  isUserStackLoaded,
  saveUserStackProfile,
} from '../utils/userStack.js'

const AssetProfileContext = createContext(null)

export function AssetProfileProvider({ children }) {
  const { status: authStatus } = useAuth()
  const [profile, setProfile] = useState(null)
  const [matchScores, setMatchScores] = useState({})
  const [isLocked, setIsLocked] = useState(false)
  const [sessionWarnOpen, setSessionWarnOpen] = useState(false)
  const [flow, setFlow] = useState(null)
  const [wizardProfile, setWizardProfile] = useState(null)
  const [rememberOnServer, setRememberOnServer] = useState(() => getRememberProfileOnServer())
  const hydratedRef = useRef(false)

  const isLoaded = profile !== null && !isLocked
  const assetAware = isLoaded

  const syncRememberState = useCallback(() => {
    setRememberOnServer(getRememberProfileOnServer())
  }, [])

  const clearProfile = useCallback(() => {
    setProfile(null)
    setMatchScores({})
    setIsLocked(false)
    setFlow(null)
    setWizardProfile(null)
  }, [])

  const lockSession = useCallback(() => {
    setProfile(null)
    setMatchScores({})
    setIsLocked(true)
    setSessionWarnOpen(false)
    setFlow(null)
    setWizardProfile(null)
  }, [])

  const applyProfile = useCallback(async (nextProfile) => {
    setProfile(nextProfile)
    setIsLocked(false)
    setFlow(null)
    setWizardProfile(null)
    const assets = profileToMatchAssets(nextProfile)
    if (!assets.length) {
      setMatchScores({})
    } else {
      try {
        const res = await fetchCveAssetMatch(assets)
        setMatchScores(res?.matches || {})
      } catch {
        setMatchScores({})
      }
    }
    if (getRememberProfileOnServer()) {
      try {
        await saveUserStackProfile(nextProfile)
      } catch (err) {
        notifyApiError(err)
      }
    }
    try {
      window.dispatchEvent(new CustomEvent('briefr-profile-change'))
    } catch {}
  }, [])

  const tryHydrateFromServer = useCallback(async () => {
    if (authStatus !== 'authed') return
    if (hydratedRef.current || profile) return
    if (!isUserStackLoaded() || !isUserPreferencesLoaded()) return
    if (!getRememberProfileOnServer()) return
    const saved = getSavedStackProfile()
    if (!saved) return
    hydratedRef.current = true
    await applyProfile(saved)
  }, [authStatus, profile, applyProfile])

  const handleRememberChange = useCallback(async (enabled) => {
    const previous = getRememberProfileOnServer()
    setRememberOnServer(enabled)
    try {
      await setRememberProfileOnServer(enabled, enabled ? profile : null)
    } catch (err) {
      setRememberOnServer(previous)
      notifyApiError(err)
    }
  }, [profile])

  const openProfileFlow = useCallback(() => {
    if (profile && !isLocked) {
      setFlow('manage')
      return
    }
    setWizardProfile(null)
    setFlow('warning')
  }, [profile, isLocked])

  const loadProfileFromFile = useCallback(async (file) => {
    const parsed = await parseProfileFile(file)
    await applyProfile(parsed)
  }, [applyProfile])

  const startWizard = useCallback((initial = null) => {
    setWizardProfile(initial)
    setFlow('wizard')
  }, [])

  useInactivityTimeout({
    enabled: isLoaded,
    onTimeout: lockSession,
    onWarning: () => setSessionWarnOpen(true),
  })

  useEffect(() => {
    if (authStatus !== 'authed') {
      hydratedRef.current = false
    }
    syncRememberState()
  }, [authStatus, syncRememberState])

  useEffect(() => {
    tryHydrateFromServer()
  }, [tryHydrateFromServer])

  useEffect(() => {
    const onData = () => {
      syncRememberState()
      tryHydrateFromServer()
    }
    window.addEventListener('briefr-stack-loaded', onData)
    window.addEventListener('briefr-preferences-loaded', onData)
    return () => {
      window.removeEventListener('briefr-stack-loaded', onData)
      window.removeEventListener('briefr-preferences-loaded', onData)
    }
  }, [syncRememberState, tryHydrateFromServer])

  useEffect(() => {
    if (!sessionWarnOpen) return undefined
    const clear = (e) => {
      if (e.target?.closest?.('.session-idle-warning')) return
      setSessionWarnOpen(false)
    }
    window.addEventListener('mousedown', clear)
    window.addEventListener('keydown', clear)
    return () => {
      window.removeEventListener('mousedown', clear)
      window.removeEventListener('keydown', clear)
    }
  }, [sessionWarnOpen])

  const value = useMemo(
    () => ({
      profile,
      matchScores,
      isLoaded,
      assetAware,
      isLocked,
      rememberOnServer,
      openProfileFlow,
      clearProfile,
      loadProfileFromFile,
      getMatchScore: (cveId) => matchScores[cveId] || 0,
    }),
    [
      profile,
      matchScores,
      isLoaded,
      assetAware,
      isLocked,
      rememberOnServer,
      openProfileFlow,
      clearProfile,
      loadProfileFromFile,
    ],
  )

  return (
    <AssetProfileContext.Provider value={value}>
      {children}
      {flow === 'warning' && (
        <AssetWarning
          rememberOnServer={rememberOnServer}
          onRememberChange={handleRememberChange}
          showRememberToggle={authStatus === 'authed'}
          onAccept={() => startWizard(null)}
          onUpload={loadProfileFromFile}
          onSkip={() => setFlow(null)}
          onClose={() => setFlow(null)}
        />
      )}
      {flow === 'manage' && (
        <AssetProfileManage
          rememberOnServer={rememberOnServer}
          onRememberChange={handleRememberChange}
          showRememberToggle={authStatus === 'authed'}
          onUpdate={() => startWizard(profile)}
          onUpload={loadProfileFromFile}
          onKeep={() => setFlow(null)}
          onClose={() => setFlow(null)}
        />
      )}
      {flow === 'wizard' && (
        <AssetWizard
          initialProfile={wizardProfile}
          onComplete={applyProfile}
          onCancel={() => setFlow(null)}
        />
      )}
      {sessionWarnOpen && profile && !isLocked && (
        <SessionIdleWarning
          profile={profile}
          onDismiss={() => setSessionWarnOpen(false)}
        />
      )}
      {isLocked && (
        <SessionLockOverlay
          onLoadProfile={loadProfileFromFile}
          onContinueWithoutStack={() => setIsLocked(false)}
        />
      )}
    </AssetProfileContext.Provider>
  )
}

export function useAssetProfile() {
  const ctx = useContext(AssetProfileContext)
  if (!ctx) {
    throw new Error('useAssetProfile must be used within AssetProfileProvider')
  }
  return ctx
}

export function useAssetProfileOptional() {
  return useContext(AssetProfileContext)
}
