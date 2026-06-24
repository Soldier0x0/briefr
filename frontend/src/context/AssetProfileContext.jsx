import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import AssetWarning from '../components/AssetWarning.jsx'
import AssetProfileManage from '../components/AssetProfileManage.jsx'
import AssetWizard from '../components/AssetWizard.jsx'
import SessionLockOverlay from '../components/SessionLockOverlay.jsx'
import SessionIdleWarning from '../components/SessionIdleWarning.jsx'
import { fetchCveAssetMatch } from '../api.js'
import { useInactivityTimeout } from '../hooks/useInactivityTimeout.js'
import { parseProfileFile, profileToMatchAssets } from '../utils/assetProfileIo.js'

const AssetProfileContext = createContext(null)

export function AssetProfileProvider({ children }) {
  const [profile, setProfile] = useState(null)
  const [matchScores, setMatchScores] = useState({})
  const [isLocked, setIsLocked] = useState(false)
  const [sessionWarnOpen, setSessionWarnOpen] = useState(false)
  const [flow, setFlow] = useState(null)
  const [wizardProfile, setWizardProfile] = useState(null)

  const isLoaded = profile !== null && !isLocked
  const assetAware = isLoaded

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
      return
    }
    try {
      const res = await fetchCveAssetMatch(assets)
      setMatchScores(res?.matches || {})
    } catch {
      setMatchScores({})
    }
    try {
      window.dispatchEvent(new CustomEvent('briefr-profile-change'))
    } catch {}
  }, [])

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
    if (!sessionWarnOpen) return undefined
    const clear = () => setSessionWarnOpen(false)
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
          onAccept={() => startWizard(null)}
          onUpload={loadProfileFromFile}
          onSkip={() => setFlow(null)}
          onClose={() => setFlow(null)}
        />
      )}
      {flow === 'manage' && (
        <AssetProfileManage
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
