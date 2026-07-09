import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react'
import { extractIndicatorsFromCve } from '../utils/extractIndicatorsFromCve.js'
import { fetchOTXPulseIocs } from '../api.js'
import {
  INV_TYPE_TECHNIQUE,
  investigationPivotBadge,
  techniqueSummaryParts,
  TECHNIQUE_TAXONOMY,
} from '../utils/investigationLabels.js'

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
  const badge = investigationPivotBadge(item)
  return `${badge} ${item.id}`
}

function buildThreadSummary(items) {
  const counts = { cve: 0, ioc: 0, actor: 0, technique: 0 }
  items.forEach(i => {
    if (i.type === INV_TYPES.CVE) counts.cve += 1
    else if (i.type === INV_TYPES.IOC) counts.ioc += 1
    else if (i.type === INV_TYPES.ACTOR) counts.actor += 1
    else if (i.type === INV_TYPES.TECHNIQUE) counts.technique += 1
  })
  const parts = []
  if (counts.cve) parts.push(`${counts.cve} CVE${counts.cve > 1 ? 's' : ''}`)
  if (counts.ioc) parts.push(`${counts.ioc} IOC${counts.ioc > 1 ? 's' : ''}`)
  if (counts.actor) parts.push(`${counts.actor} actor${counts.actor > 1 ? 's' : ''}`)
  const techniqueParts = techniqueSummaryParts(items)
  if (techniqueParts.length) parts.push(...techniqueParts)
  return parts.join(' · ') || 'No items'
}

export function InvestigationProvider({ children, navigation }) {
  const [items, setItems] = useState([])
  const [startTime, setStartTime] = useState(null)
  const [panelExpanded, setPanelExpanded] = useState(true)
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false)
  const [pivotNotice, setPivotNotice] = useState(null)
  const itemsRef = useRef(items)
  itemsRef.current = items

  const isActive = items.length > 0
  const showPanel = items.length >= 1
  const threadSummary = useMemo(() => buildThreadSummary(items), [items])
  const cveIdsInThread = useMemo(
    () => new Set(items.filter(i => i.type === INV_TYPES.CVE).map(i => i.id)),
    [items],
  )
  const isCveInThread = useCallback(
    (cveId) => !!(cveId && cveIdsInThread.has(cveId)),
    [cveIdsInThread],
  )

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

  const startInvestigation = useCallback((cve) => {
    if (!cve?.cve_id) return
    const wasEmpty = itemsRef.current.length === 0
    if (!itemsRef.current.some(i => i.type === INV_TYPES.CVE && i.id === cve.cve_id)) {
      ensureCveInThread(cve, INV_SOURCES.FEED)
    }
    setPanelExpanded(true)
    setMobileSheetOpen(true)
    if (wasEmpty) {
      setPivotNotice('Investigation started — CVEs, IOC lookups, and links you follow will be included in the PDF export.')
    }
    navigation?.clearIocPrefill?.()
    navigation?.resetIocSession?.()
  }, [ensureCveInThread, navigation])

  const recordIocPivot = useCallback((ip, from) => {
    const fromItem = from || itemsRef.current[itemsRef.current.length - 1]
    const exists = itemsRef.current.some(
      i => i.type === INV_TYPES.IOC && i.id === ip,
    )
    if (exists) return
    recordItem({
      type: INV_TYPES.IOC,
      id: ip,
      title: ip,
      description: `Indicator lookup: ${ip}`,
      source: INV_SOURCES.IOC,
      pivotFrom: fromItem,
    })
  }, [recordItem])

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
    recordIocPivot(ip, from)
    navigation?.setActiveTab?.('ioc')
    navigation?.setIocPrefill?.({
      value: ip,
      indicators: [{ type: 'ip', value: ip }],
      trigger: Date.now(),
    })
  }, [recordItem, recordIocPivot, navigation])

  const pivotToIocFromCve = useCallback((cve) => {
    if (!cve?.cve_id) return
    ensureCveInThread(cve, INV_SOURCES.FEED)
    const indicators = extractIndicatorsFromCve(cve)
    const fromCve = itemsRef.current.find(
      i => i.type === INV_TYPES.CVE && i.id === cve.cve_id,
    )
    navigation?.setActiveTab?.('ioc')
    navigation?.setIocPrefill?.({
      indicators,
      value: indicators[0]?.value,
      fromCveId: cve.cve_id,
      pivotFrom: fromCve,
      trigger: Date.now(),
    })
  }, [ensureCveInThread, navigation])

  const pivotToOtxPulse = useCallback(async (pulse, cve) => {
    if (!pulse?.pulse_id) return
    setPivotNotice(null)
    const fromCve = ensureCveInThread(cve, INV_SOURCES.DRAWER)
    try {
      const res = await fetchOTXPulseIocs(pulse.pulse_id)
      const indicators = res?.data?.indicators || []
      if (!indicators.length) {
        setPivotNotice('No IOCs found for this campaign pulse.')
        return
      }
      navigation?.setActiveTab?.('ioc')
      navigation?.setIocPrefill?.({ indicators: indicators.slice(0, 3), value: indicators[0]?.value, fromCveId: cve?.cve_id, pivotFrom: fromCve, trigger: Date.now() })
    } catch {
      setPivotNotice('Could not load IOCs for this campaign pulse.')
    }
  }, [ensureCveInThread, navigation])

  const pivotToCampaign = useCallback((campaign, anchorCve) => {
    if (!campaign) return
    setPivotNotice(null)
    const anchor = ensureCveInThread(anchorCve, INV_SOURCES.DRAWER)
    if (!anchor) return
    const anchorId = typeof anchorCve === 'string' ? anchorCve : anchorCve?.cve_id
    const memberIds = (campaign.members || []).filter(id => id && id !== anchorId)
    let added = 0
    for (const cveId of memberIds) {
      if (itemsRef.current.some(i => i.type === INV_TYPES.CVE && i.id === cveId)) continue
      recordItem({
        type: INV_TYPES.CVE,
        id: cveId,
        title: cveId,
        description: campaign.summary || campaign.label || `Campaign cluster ${campaign.campaign_id || ''}`.trim(),
        source: INV_SOURCES.DRAWER,
        pivotFrom: anchor,
        meta: { campaign_id: campaign.campaign_id, lifecycle: campaign.lifecycle },
      })
      added += 1
    }
    setPanelExpanded(true)
    setMobileSheetOpen(true)
    if (added === 0) {
      setPivotNotice('All linked CVEs from this campaign are already in the investigation.')
    } else {
      setPivotNotice(`Added ${added} linked CVE${added === 1 ? '' : 's'} from campaign cluster.`)
    }
  }, [ensureCveInThread, recordItem])

  const openCveById = useCallback((cveId) => { if (!cveId) return; navigation?.openCve?.(cveId) }, [navigation])

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
      meta: { taxonomy: TECHNIQUE_TAXONOMY.ATLAS },
    })
  }, [recordItem])

  const value = useMemo(() => ({
    items,
    startTime,
    isActive,
    showPanel,
    threadSummary,
    panelExpanded,
    setPanelExpanded,
    mobileSheetOpen,
    setMobileSheetOpen,
    lastItem,
    recordItem,
    clearInvestigation,
    ensureCveInThread,
    startInvestigation,
    isCveInThread,
    recordIocPivot,
    pivotToIoc,
    pivotToIocFromCve,
    pivotToOtxPulse,
    pivotToCampaign,
    openCveById,
    pivotToAtlasActor,
    pivotToCveFromAtlas,
    pivotToTechnique,
    pivotLabel,
    pivotNotice,
    clearPivotNotice: () => setPivotNotice(null),
  }), [
    items,
    startTime,
    isActive,
    showPanel,
    threadSummary,
    panelExpanded,
    mobileSheetOpen,
    lastItem,
    recordItem,
    clearInvestigation,
    ensureCveInThread,
    startInvestigation,
    isCveInThread,
    recordIocPivot,
    pivotToIoc,
    pivotToIocFromCve,
    pivotToOtxPulse,
    pivotToCampaign,
    openCveById,
    pivotToAtlasActor,
    pivotToCveFromAtlas,
    pivotToTechnique,
    pivotNotice,
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
