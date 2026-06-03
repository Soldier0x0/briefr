import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react'

export const INV_TYPES = {
  CVE: 'cve',
  IOC: 'ioc',
  ACTOR: 'actor',
  TECHNIQUE: 'technique',
}

export const INV_SOURCES = {
  FEED: 'feed',
  IOC: 'ioc',
  ATLAS: 'atlas',
  DRAWER: 'drawer',
}

const InvestigationContext = createContext(null)

function pivotLabel(item) {
  if (!item) return null
  const badge = item.type === INV_TYPES.CVE ? 'CVE'
    : item.type === INV_TYPES.IOC ? 'IOC'
      : item.type === INV_TYPES.ACTOR ? 'ACTOR'
        : 'AI'
  return `${badge} ${item.id}`
}

export function InvestigationProvider({ children, navigation }) {
  const [items, setItems] = useState([])
  const [startTime, setStartTime] = useState(null)
  const [panelExpanded, setPanelExpanded] = useState(true)
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false)
  const itemsRef = useRef(items)
  itemsRef.current = items

  const isActive = items.length > 0
  const showPanel = items.length >= 2

  const lastItem = items.length ? items[items.length - 1] : null

  const recordItem = useCallback((entry) => {
    const item = {
      key: `${entry.type}:${entry.id}:${Date.now()}`,
      type: entry.type,
      id: entry.id,
      title: entry.title || entry.id,
      description: entry.description || '',
      timestamp: Date.now(),
      source: entry.source || INV_SOURCES.FEED,
      pivotFrom: entry.pivotFrom || null,
      meta: entry.meta || null,
    }
    setItems(prev => {
      if (!prev.length) setStartTime(Date.now())
      return [...prev, item]
    })
    return item
  }, [])

  const clearInvestigation = useCallback(() => {
    setItems([])
    setStartTime(null)
    setMobileSheetOpen(false)
    navigation?.clearAtlasFilter?.()
  }, [navigation])

  const ensureCveInThread = useCallback((cve, source = INV_SOURCES.DRAWER) => {
    const id = typeof cve === 'string' ? cve : cve?.cve_id
    if (!id) return null
    const exists = itemsRef.current.some(i => i.type === INV_TYPES.CVE && i.id === id)
    if (exists) return itemsRef.current.find(i => i.type === INV_TYPES.CVE && i.id === id)
    const title = typeof cve === 'object' ? cve.cve_id : cve
    const desc = typeof cve === 'object'
      ? (cve.summary || cve.description || '').slice(0, 120)
      : ''
    return recordItem({
      type: INV_TYPES.CVE,
      id,
      title,
      description: desc,
      source,
      pivotFrom: null,
      meta: typeof cve === 'object' ? { severity: cve.severity, is_kev: cve.is_kev } : null,
    })
  }, [recordItem])

  const onCveDrawerOpened = useCallback((cve) => {
    if (!cve?.cve_id) return
    if (!itemsRef.current.length) {
      ensureCveInThread(cve, INV_SOURCES.DRAWER)
      return
    }
    const already = itemsRef.current.some(i => i.type === INV_TYPES.CVE && i.id === cve.cve_id)
    if (!already) {
      const prev = itemsRef.current[itemsRef.current.length - 1]
      recordItem({
        type: INV_TYPES.CVE,
        id: cve.cve_id,
        title: cve.cve_id,
        description: (cve.summary || cve.description || '').slice(0, 120),
        source: INV_SOURCES.DRAWER,
        pivotFrom: prev,
        meta: { severity: cve.severity, is_kev: cve.is_kev },
      })
    }
  }, [ensureCveInThread, recordItem])

  const pivotToIoc = useCallback((ip, cveContext) => {
    const from = cveContext || itemsRef.current[itemsRef.current.length - 1]
    if (from?.type === INV_TYPES.CVE && from.id) {
      const hasCve = itemsRef.current.some(i => i.type === INV_TYPES.CVE && i.id === from.id)
      if (!hasCve) {
        recordItem({
          type: INV_TYPES.CVE,
          id: from.id,
          title: from.id,
          description: from.description || '',
          source: INV_SOURCES.DRAWER,
          pivotFrom: null,
        })
      }
    }
    recordItem({
      type: INV_TYPES.IOC,
      id: ip,
      title: ip,
      description: `Indicator lookup: ${ip}`,
      source: INV_SOURCES.IOC,
      pivotFrom: from,
    })
    navigation?.setActiveTab?.('ioc')
    navigation?.setIocPrefill?.(ip)
  }, [recordItem, navigation])

  const pivotToAtlasActor = useCallback((actorName, fromItem) => {
    const from = fromItem || itemsRef.current[itemsRef.current.length - 1]
    recordItem({
      type: INV_TYPES.ACTOR,
      id: actorName,
      title: actorName,
      description: `Threat actor / campaign context`,
      source: INV_SOURCES.ATLAS,
      pivotFrom: from,
    })
    navigation?.setActiveTab?.('atlas')
    navigation?.setAtlasActorFilter?.(actorName)
  }, [recordItem, navigation])

  const pivotToCveFromAtlas = useCallback((cveId, studyName) => {
    const from = itemsRef.current[itemsRef.current.length - 1]
    recordItem({
      type: INV_TYPES.CVE,
      id: cveId,
      title: cveId,
      description: studyName ? `From case study: ${studyName}` : 'ATLAS case study reference',
      source: INV_SOURCES.ATLAS,
      pivotFrom: from,
    })
    navigation?.setActiveTab?.('feed')
    navigation?.openCve?.(cveId)
  }, [recordItem, navigation])

  const pivotToTechnique = useCallback((techniqueId, name, fromItem) => {
    const from = fromItem || itemsRef.current[itemsRef.current.length - 1]
    recordItem({
      type: INV_TYPES.TECHNIQUE,
      id: techniqueId,
      title: `${techniqueId} — ${name || ''}`.trim(),
      description: 'MITRE ATLAS technique',
      source: INV_SOURCES.ATLAS,
      pivotFrom: from,
    })
  }, [recordItem])

  const value = useMemo(() => ({
    items,
    startTime,
    isActive,
    showPanel,
    panelExpanded,
    setPanelExpanded,
    mobileSheetOpen,
    setMobileSheetOpen,
    lastItem,
    recordItem,
    clearInvestigation,
    ensureCveInThread,
    onCveDrawerOpened,
    pivotToIoc,
    pivotToAtlasActor,
    pivotToCveFromAtlas,
    pivotToTechnique,
    pivotLabel,
  }), [
    items,
    startTime,
    isActive,
    showPanel,
    panelExpanded,
    mobileSheetOpen,
    lastItem,
    recordItem,
    clearInvestigation,
    ensureCveInThread,
    onCveDrawerOpened,
    pivotToIoc,
    pivotToAtlasActor,
    pivotToCveFromAtlas,
    pivotToTechnique,
  ])

  return (
    <InvestigationContext.Provider value={value}>
      {children}
    </InvestigationContext.Provider>
  )
}

export function useInvestigation() {
  const ctx = useContext(InvestigationContext)
  if (!ctx) {
    throw new Error('useInvestigation must be used within InvestigationProvider')
  }
  return ctx
}

export function useInvestigationOptional() {
  return useContext(InvestigationContext)
}
