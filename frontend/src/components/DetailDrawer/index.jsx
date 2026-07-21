import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchCVE,
  fetchCVEDrawerBundle,
  fetchCVECorrelation,
  fetchCVEDetection,
  fetchCVEGreynoiseScans,
  fetchCVERisk,
  fetchCorrelationSuppressions,
  fetchCorrelationFeedback,
  confirmCVECorrelation,
  fetchIOCUsage,
  restoreCVECorrelation,
  suppressCVECorrelation,
} from '../../api.js'
import { buildSingleReport, copyToClipboard } from '../../utils/report.js'
import { notifyCopyFailure, notifyCopySuccess, notifyExportError, notifyExportSuccess } from '../Toast.jsx'
import PdfExportModal from '../PdfExportModal.jsx'
import { useInvestigationOptional } from '../../context/InvestigationContext.jsx'
import { useAssetProfileOptional } from '../../context/AssetProfileContext.jsx'
import { profileToMatchAssets } from '../../utils/assetProfileIo.js'
import { applyCorrelationEscalationToRiskScore } from '../../scoring/riskScore.js'
import { setMomentumScore } from '../../utils/momentumCache.js'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { campaignBadgeTooltip, campaignLifecycleClass, primaryCampaignChip } from '../../utils/correlationPresentation.js'
import { shouldIgnoreGlobalShortcut } from '../../utils/keyboardScope.js'
import useModalLayer from '../../hooks/useModalLayer.js'
import { severityColor } from './helpers.js'
import { severityTooltip } from '../../utils/severitySemantics.js'
import TabOverview from './OverviewTab.jsx'
import TabIntel from './IntelTab.jsx'
import TabDetect from './DetectTab.jsx'
import TabRelated from './RelatedTab.jsx'
import CorrelationSuppressModal from './CorrelationSuppressModal.jsx'
import ControlTooltip from '../ControlTooltip.jsx'
import '../DetailDrawer.css'


class DrawerTabErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error) {
    console.error('Drawer tab render failed:', error)
  }

  render() {
    if (this.state.error) {
      return (
        <p className="drawer-intel-empty mono">
          This section could not be displayed. Close and reopen the CVE, or refresh the page.
        </p>
      )
    }
    return this.props.children
  }
}


const TABS = [
  { id: 'overview', label: 'OVERVIEW', title: 'Scores, timeline, affected products, and technical details' },
  { id: 'intel',    label: 'INTEL',    title: 'Threat intelligence: PoC links, CISA KEV data, MITRE ATT&CK techniques' },
  { id: 'detect',   label: 'DETECT',   title: 'Detection rules and signatures for your SIEM or EDR' },
  { id: 'related',  label: 'RELATED',  title: 'Related CVEs and similar vulnerabilities' },
]

export default function DetailDrawer({ cve, loading = false, error = null, onRetry, onClose, onCveReplace, watchlistState = null, onWatchlistChange }) {
  const [activeTab, setActiveTab] = useState('overview')
  const [reportOpen, setReportOpen] = useState(false)
  const [actionsMenuOpen, setActionsMenuOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [sentences, setSentences] = useState(null)
  const [sentencesLoading, setSentencesLoading] = useState(false)
  const [epssHistory, setEpssHistory] = useState([])
  const [epssLoading, setEpssLoading] = useState(false)
  const [related, setRelated] = useState([])
  const [relatedMethod, setRelatedMethod] = useState('')
  const [relatedNews, setRelatedNews] = useState([])
  const [relatedLoading, setRelatedLoading] = useState(false)
  const [correlation, setCorrelation] = useState(null)
  const [correlationLoading, setCorrelationLoading] = useState(false)
  const [correlationSuppressions, setCorrelationSuppressions] = useState([])
  const [correlationFeedback, setCorrelationFeedback] = useState([])
  const [suppressModal, setSuppressModal] = useState(null)
  const [suppressSubmitting, setSuppressSubmitting] = useState(false)
  const [greynoiseScans, setGreynoiseScans] = useState([])
  const [greynoiseLoading, setGreynoiseLoading] = useState(false)
  const [greynoiseLoaded, setGreynoiseLoaded] = useState(false)
  const [greynoiseQuota, setGreynoiseQuota] = useState(null)
  const [detection, setDetection] = useState(null)
  const [detectionLoading, setDetectionLoading] = useState(false)
  const [detectionError, setDetectionError] = useState(null)
  const detectionFetchedRef = useRef(false)
  const detectionCancelRef = useRef(null)
  const [momentumData, setMomentumData] = useState(null)
  const [riskScore, setRiskScore] = useState(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState(null)
  const [backStack, setBackStack] = useState([])
  const [pdfModalOpen, setPdfModalOpen] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  const [pdfError, setPdfError] = useState(null)
  const reportRef = useRef(null)
  const actionsMenuRef = useRef(null)
  const epssSparklineRef = useRef(null)
  const sheetRef = useRef(null)
  const navigatingRef = useRef(false)
  const isOpen = !!cve

  // Trap Tab inside the drawer while open; restore focus to the originating
  // card on close. Escape stays owned by the global App handler.
  useModalLayer(isOpen, sheetRef)
  const investigation = useInvestigationOptional()
  const assetCtx = useAssetProfileOptional()

  useEffect(() => {
    if (!cve?.cve_id) {
      setRiskScore(null)
      setRiskLoading(false)
      setRiskError(null)
      return
    }
    let cancelled = false
    setRiskLoading(true)
    setRiskError(null)
    const payload =
      assetCtx?.isLoaded && assetCtx?.profile
        ? {
            profile: assetCtx.profile,
            assets: profileToMatchAssets(assetCtx.profile),
          }
        : {}
    fetchCVERisk(cve.cve_id, payload)
      .then(data => {
        if (cancelled) return
        if (!data) {
          setRiskScore(null)
          return
        }
        const legacy = data.legacy_risk_v11b || {}
        setRiskScore({
          threat: data.threat,
          environment: data.environment,
          operational_priority: data.operational_priority,
          legacy_risk_v11b: legacy,
          momentum: data.momentum,
          hasProfile: data.hasProfile,
          momentumScore: data.momentumScore,
          total: legacy.total,
          components: legacy.components,
          assetMatchType: legacy.assetMatchType,
          weights: legacy.weights,
        })
      })
      .catch((err) => {
        console.error('Failed to fetch CVE risk:', err)
        if (!cancelled) {
          setRiskScore(null)
          setRiskError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setRiskLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [cve?.cve_id, assetCtx?.profile, assetCtx?.isLoaded])

  useEffect(() => {
    investigation?.clearPivotNotice?.()
  }, [cve?.cve_id, investigation])

  useEffect(() => {
    if (!cve?.cve_id) {
      setSentences(null)
      setSentencesLoading(false)
      setEpssHistory([])
      setEpssLoading(false)
      setRelated([])
      setRelatedMethod('')
      setRelatedNews([])
      setRelatedLoading(false)
      setCorrelation(null)
      setCorrelationLoading(false)
      setCorrelationSuppressions([])
      setCorrelationFeedback([])
      setMomentumData(null)
      return
    }
    let cancelled = false
    setSentences(null)
    setSentencesLoading(true)
    setEpssLoading(true)
    setRelatedLoading(true)
    setCorrelation(null)
    setCorrelationLoading(true)
    const sector = assetCtx?.profile?.environment?.industry || ''
    Promise.all([
      fetchCVEDrawerBundle(cve.cve_id, sector),
      fetchCorrelationSuppressions(cve.cve_id).catch(() => ({ suppressions: [] })),
      fetchCorrelationFeedback(cve.cve_id).catch(() => ({ feedback: [] })),
    ])
      .then(([bundle, supData, fbData]) => {
        if (cancelled) return
        setSentences(bundle.sentences || null)
        setEpssHistory(Array.isArray(bundle.epss_history) ? bundle.epss_history : [])
        const relatedPayload = bundle.related || {}
        setRelated(relatedPayload.data || [])
        setRelatedMethod(relatedPayload.meta?.method || '')
        setRelatedNews(Array.isArray(bundle.related_news) ? bundle.related_news : [])
        setCorrelation(bundle.correlation || null)
        setCorrelationSuppressions(supData?.suppressions || [])
        setCorrelationFeedback(fbData?.feedback || [])
        const momentum = bundle.momentum
        if (momentum && typeof momentum.momentum_score === 'number') {
          setMomentumData(momentum)
          setMomentumScore(cve.cve_id, momentum.momentum_score)
        } else {
          setMomentumData(momentum || null)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSentences(null)
          setEpssHistory([])
          setRelated([])
          setRelatedMethod('')
          setRelatedNews([])
          setCorrelation(null)
          setCorrelationSuppressions([])
          setCorrelationFeedback([])
          setMomentumData(null)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSentencesLoading(false)
          setEpssLoading(false)
          setRelatedLoading(false)
          setCorrelationLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [cve?.cve_id, assetCtx?.profile?.environment?.industry])

  useEffect(() => {
    if (!isOpen) {
      setBackStack([])
      return
    }
    if (navigatingRef.current) {
      navigatingRef.current = false
      return
    }
    setBackStack([])
  }, [cve?.cve_id, isOpen])

  // Reset detection + momentum when CVE changes
  useEffect(() => {
    setDetection(null)
    setDetectionLoading(false)
    setDetectionError(null)
    detectionFetchedRef.current = false
    detectionCancelRef.current?.()
    detectionCancelRef.current = null
    setMomentumData(null)
  }, [cve?.cve_id])

  const loadDetection = useCallback(() => {
    if (!cve?.cve_id) return undefined
    detectionCancelRef.current?.()
    let cancelled = false
    const cancel = () => { cancelled = true }
    detectionCancelRef.current = cancel
    setDetectionLoading(true)
    setDetectionError(null)
    const product = cve.affected_products?.[0]?.split(':')?.[1] || ''
    fetchCVEDetection(cve.cve_id, product)
      .then(data => {
        if (!cancelled) {
          setDetection(data)
          setDetectionError(null)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setDetection(null)
          setDetectionError(err?.message || 'Request failed')
        }
      })
      .finally(() => {
        if (!cancelled) setDetectionLoading(false)
        if (detectionCancelRef.current === cancel) detectionCancelRef.current = null
      })
    return cancel
  }, [cve?.cve_id, cve?.affected_products])

  const displayRiskScore = useMemo(
    () => applyCorrelationEscalationToRiskScore(riskScore, correlation),
    [riskScore, correlation],
  )

  // Detection: lazy-fetch when Detect tab first activated
  useEffect(() => {
    if (activeTab !== 'detect' || !cve?.cve_id || detectionFetchedRef.current) return
    detectionFetchedRef.current = true
    const cleanup = loadDetection()
    return cleanup
  }, [activeTab, cve?.cve_id, loadDetection])

  async function refreshCorrelation() {
    if (!cve?.cve_id) return
    const sector = assetCtx?.profile?.environment?.industry || ''
    const [data, supData, fbData] = await Promise.all([
      fetchCVECorrelation(cve.cve_id, sector),
      fetchCorrelationSuppressions(cve.cve_id).catch(() => ({ suppressions: [] })),
      fetchCorrelationFeedback(cve.cve_id).catch(() => ({ feedback: [] })),
    ])
    setCorrelation(data)
    setCorrelationSuppressions(supData?.suppressions || [])
    setCorrelationFeedback(fbData?.feedback || [])
  }

  async function handleConfirmCorrelation(body) {
    if (!cve?.cve_id || !body) return
    try {
      await confirmCVECorrelation(cve.cve_id, body)
      await refreshCorrelation()
    } catch {
      /* best-effort */
    }
  }

  function handleRequestSuppressCorrelation(body, peerCve) {
    setSuppressModal({ body, peerCve: peerCve || body?.key?.cve_id_b || '' })
  }

  async function handleConfirmSuppress(bodyWithReason) {
    if (!cve?.cve_id || !bodyWithReason) return
    setSuppressSubmitting(true)
    try {
      await suppressCVECorrelation(cve.cve_id, bodyWithReason)
      setSuppressModal(null)
      await refreshCorrelation()
    } catch {
      /* best-effort */
    } finally {
      setSuppressSubmitting(false)
    }
  }

  async function handleRestoreSuppression(suppression) {
    if (!cve?.cve_id || !suppression) return
    const scope = suppression.scope
    const sk = suppression.scope_key || ''
    try {
      await restoreCVECorrelation(cve.cve_id, {
        scope,
        cve_id_b: scope === 'infrastructure' || scope === 'cve_pair' ? sk : '',
        campaign_id: scope === 'campaign_id' ? sk : '',
        pulse_id: scope === 'pulse_id' ? sk : '',
      })
      await refreshCorrelation()
    } catch {
      /* best-effort */
    }
  }

  useEffect(() => {
    if (!cve?.cve_id) {
      setGreynoiseScans([])
      setGreynoiseLoading(false)
      setGreynoiseLoaded(false)
      setGreynoiseQuota(null)
      return
    }
    setGreynoiseScans([])
    setGreynoiseLoading(false)
    setGreynoiseLoaded(false)
  }, [cve?.cve_id])

  useEffect(() => {
    if (activeTab !== 'intel' || !cve?.greynoise_configured) return
    let cancelled = false
    fetchIOCUsage()
      .then(data => {
        if (cancelled) return
        const gn = (data?.services || []).find(s => s.service === 'greynoise')
        setGreynoiseQuota(gn || null)
      })
      .catch(() => {
        if (!cancelled) setGreynoiseQuota(null)
      })
    return () => { cancelled = true }
  }, [activeTab, cve?.cve_id, cve?.greynoise_configured])

  const loadGreynoiseScans = useCallback(async () => {
    if (!cve?.cve_id) return
    setGreynoiseLoading(true)
    try {
      const [data, usage] = await Promise.all([
        fetchCVEGreynoiseScans(cve.cve_id),
        fetchIOCUsage().catch(() => null),
      ])
      setGreynoiseScans(Array.isArray(data?.scans) ? data.scans : [])
      if (usage?.services) {
        const gn = usage.services.find(s => s.service === 'greynoise')
        setGreynoiseQuota(gn || null)
      }
    } catch {
      setGreynoiseScans([])
    } finally {
      setGreynoiseLoading(false)
      setGreynoiseLoaded(true)
    }
  }, [cve?.cve_id])

  useEffect(() => {
    if (isOpen) {
      document.body.classList.add('briefr-drawer-open')
      document.body.style.overflow = 'hidden'
      setActiveTab('overview')
      setReportOpen(false)
      setActionsMenuOpen(false)
    } else {
      document.body.classList.remove('briefr-drawer-open')
      document.body.style.overflow = ''
    }
    return () => {
      document.body.classList.remove('briefr-drawer-open')
      document.body.style.overflow = ''
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return undefined

    function onWheel(e) {
      const panel = e.target.closest?.('.drawer-tab-panel')
      if (!panel || !sheetRef.current?.contains(panel)) {
        e.preventDefault()
        return
      }
      const { scrollTop, scrollHeight, clientHeight } = panel
      const atTop = scrollTop <= 0 && e.deltaY < 0
      const atBottom = scrollTop + clientHeight >= scrollHeight - 1 && e.deltaY > 0
      if (atTop || atBottom) {
        e.preventDefault()
        e.stopPropagation()
      }
    }

    document.addEventListener('wheel', onWheel, { passive: false, capture: true })
    return () => document.removeEventListener('wheel', onWheel, { capture: true })
  }, [isOpen])

  useEffect(() => {
    if (!reportOpen) return
    function onDocClick(e) {
      if (reportRef.current && !reportRef.current.contains(e.target)) {
        setReportOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [reportOpen])

  useEffect(() => {
    if (!actionsMenuOpen) return
    function onDocClick(e) {
      if (actionsMenuRef.current && !actionsMenuRef.current.contains(e.target)) {
        setActionsMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [actionsMenuOpen])

  async function handleCopyMarkdown() {
    if (!cve) return
    const ok = await copyToClipboard(buildSingleReport(cve))
    if (ok) {
      setCopied(true)
      setReportOpen(false)
      notifyCopySuccess(`Markdown report copied for ${cve.cve_id}`)
      setTimeout(() => setCopied(false), 2000)
    } else {
      notifyCopyFailure()
    }
  }

  function handleDownloadPdfClick() {
    setReportOpen(false)
    setPdfError(null)
    setPdfModalOpen(true)
  }

  async function handlePdfConfirm({ analystName }) {
    if (!cve) return
    setPdfBusy(true)
    setPdfError(null)
    try {
      const { downloadSingleCvePdf } = await import('../../utils/pdfReport.js')
      await downloadSingleCvePdf(cve, {
        analystName,
        sparklineElement: epssSparklineRef.current,
      })
      setPdfModalOpen(false)
      notifyExportSuccess(`PDF downloaded for ${cve.cve_id}`)
    } catch (err) {
      const message = err?.message || 'PDF generation failed.'
      setPdfError(message)
      notifyExportError(message)
    } finally {
      setPdfBusy(false)
    }
  }

  function handleBack() {
    if (!backStack.length || !onCveReplace) return
    navigatingRef.current = true
    const prev = backStack[backStack.length - 1]
    setBackStack(stack => stack.slice(0, -1))
    onCveReplace(prev)
    setActiveTab('related')
  }

  async function handleSelectRelated(cveId) {
    if (!cve || !onCveReplace) return
    navigatingRef.current = true
    setBackStack(stack => [...stack, cve])
    setActiveTab('overview')
    try {
      const full = await fetchCVE(cveId)
      onCveReplace(full)
    } catch {
      onCveReplace({ cve_id: cveId })
    }
  }

  useEffect(() => {
    if (!isOpen) return
    function onKey(e) {
      if (shouldIgnoreGlobalShortcut(e)) return
      if (e.key === 'c' || e.key === 'C') {
        e.preventDefault()
        handleCopyMarkdown()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isOpen, cve])

  if (!cve) {
    return <div className="drawer-overlay" aria-hidden="true" />
  }

  const products = Array.isArray(cve.affected_products) ? cve.affected_products : []
  const cwes = Array.isArray(cve.cwe_ids) ? cve.cwe_ids : []
  const capecIds = Array.isArray(cve.capec_ids) ? cve.capec_ids.filter(Boolean) : []
  const urls = Array.isArray(cve.source_urls) ? cve.source_urls.slice(0, 5) : []
  const sevColor = severityColor(cve.severity)
  const campaignChip = !correlationLoading ? primaryCampaignChip(correlation, cve.cve_id) : null
  const techniques = Array.isArray(cve.techniques) ? cve.techniques : []
  const canGoBack = backStack.length > 0
  const isPinned = watchlistState === 'pin'
  const hasPreviewContent = Boolean(cve.description || cve.summary)
  const showBlockingLoadingOverlay = loading && !hasPreviewContent

  return (
    <>
      <div
        className="drawer-overlay drawer-overlay-active"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className="drawer-panel drawer-panel-open"
        role="dialog"
        aria-modal="true"
        aria-label={`CVE detail: ${cve.cve_id}`}
        ref={sheetRef}
        tabIndex={-1}
      >
        <div className="drawer-sheet-handle" aria-hidden="true" />

        <div className="drawer-chrome">
          <header className="drawer-header">
            <div className="drawer-header-left">
              {canGoBack && (
                <button
                  type="button"
                  className="drawer-back-btn mono"
                  onClick={handleBack}
                  aria-label="Back to previous CVE"
                >
                  ←
                </button>
              )}
              <span className="drawer-cve-id mono">{cve.cve_id}</span>
              {cve.severity && (
                <ControlTooltip
                  text={severityTooltip(cve.severity, cve.cvss_score)}
                  trigger="hover"
                >
                  <span
                    className="drawer-sev-badge mono"
                    style={{ color: sevColor, borderColor: sevColor }}
                  >
                    {cve.severity}
                  </span>
                </ControlTooltip>
              )}
              {cve.kev_ransomware_use && (
                <ControlTooltip text="Known ransomware campaign use (CISA KEV)" trigger="hover">
                  <span
                    className="drawer-ransomware-badge mono"
                    aria-label="Known ransomware campaign use"
                  >
                    RANSOMWARE
                  </span>
                </ControlTooltip>
              )}
              {campaignChip && (
                <ControlTooltip text={campaignBadgeTooltip(campaignChip.lifecycle)} trigger="hover">
                  <span className={`drawer-campaign-badge mono ${campaignLifecycleClass(campaignChip.lifecycle)}`}>
                    Campaign · {campaignChip.linkedCount} linked CVE{campaignChip.linkedCount === 1 ? '' : 's'}
                  </span>
                </ControlTooltip>
              )}
            </div>
            <div className="drawer-header-actions">
              {onWatchlistChange && (
                <button
                  type="button"
                  className={`drawer-inv-btn mono${isPinned ? ' drawer-inv-btn-active' : ''}`}
                  onClick={() => onWatchlistChange(cve.cve_id, 'pin')}
                  aria-pressed={isPinned}
                  aria-label={isPinned ? `Unpin ${cve.cve_id}` : `Pin ${cve.cve_id}`}
                >
                  {isPinned ? 'Unpin' : 'Pin'}
                </button>
              )}
              <div className="drawer-header-actions-inline">
                {investigation && (
                  <>
                    <button
                      type="button"
                      className="drawer-inv-btn mono"
                      onClick={() => investigation.startInvestigation(cve)}
                      aria-label={`Add ${cve.cve_id} to investigation`}
                    >
                      {investigation.isCveInThread(cve.cve_id) ? 'In investigation' : 'Start investigation'}
                    </button>
                    <button
                      type="button"
                      className="drawer-inv-btn drawer-inv-btn-secondary mono"
                      onClick={() => investigation.pivotToIocFromCve(cve)}
                      aria-label={`Review indicators from ${cve.cve_id}`}
                    >
                      Review indicators
                    </button>
                    {campaignChip && investigation.pivotToCampaign && (
                      <button
                        type="button"
                        className="drawer-inv-btn drawer-inv-btn-secondary mono"
                        onClick={() => investigation.pivotToCampaign(campaignChip.campaign, cve)}
                        aria-label={`Add ${campaignChip.linkedCount} linked campaign CVEs to investigation`}
                      >
                        Add campaign
                      </button>
                    )}
                  </>
                )}
                <div className="drawer-report-wrap" ref={reportRef}>
                  <button
                    type="button"
                    className="drawer-report-btn mono"
                    onClick={() => setReportOpen(o => !o)}
                    aria-expanded={reportOpen}
                    aria-haspopup="menu"
                  >
                    REPORT
                  </button>
                  {reportOpen && (
                    <div className="drawer-report-menu" role="menu">
                      <button
                        type="button"
                        role="menuitem"
                        className="drawer-report-item mono"
                        onClick={handleDownloadPdfClick}
                      >
                        Download PDF
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        className="drawer-report-item mono"
                        onClick={handleCopyMarkdown}
                      >
                        {copied ? 'Copied!' : 'Copy Markdown'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
              <div className="drawer-actions-overflow-wrap" ref={actionsMenuRef}>
                <button
                  type="button"
                  className="drawer-actions-overflow-btn mono"
                  onClick={() => {
                    setActionsMenuOpen(o => !o)
                    if (actionsMenuOpen) setReportOpen(false)
                  }}
                  aria-label="More actions"
                  aria-expanded={actionsMenuOpen}
                  aria-haspopup="menu"
                >
                  &middot;&middot;&middot;
                </button>
                {actionsMenuOpen && (
                  <div className="drawer-actions-overflow-menu" role="menu" aria-label="CVE actions">
                    {investigation && (
                      <>
                        <button
                          type="button"
                          role="menuitem"
                          className="drawer-actions-overflow-item mono"
                          onClick={() => {
                            setActionsMenuOpen(false)
                            investigation.startInvestigation(cve)
                          }}
                        >
                          {investigation.isCveInThread(cve.cve_id) ? 'In investigation' : 'Start investigation'}
                        </button>
                        <button
                          type="button"
                          role="menuitem"
                          className="drawer-actions-overflow-item mono"
                          onClick={() => {
                            setActionsMenuOpen(false)
                            investigation.pivotToIocFromCve(cve)
                          }}
                        >
                          Review indicators
                        </button>
                        {campaignChip && investigation.pivotToCampaign && (
                          <button
                            type="button"
                            role="menuitem"
                            className="drawer-actions-overflow-item mono"
                            onClick={() => {
                              setActionsMenuOpen(false)
                              investigation.pivotToCampaign(campaignChip.campaign, cve)
                            }}
                          >
                            Add campaign
                          </button>
                        )}
                      </>
                    )}
                    <button
                      type="button"
                      role="menuitem"
                      className="drawer-actions-overflow-item mono"
                      onClick={() => {
                        setActionsMenuOpen(false)
                        handleDownloadPdfClick()
                      }}
                    >
                      Download PDF
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      className="drawer-actions-overflow-item mono"
                      onClick={() => {
                        setActionsMenuOpen(false)
                        handleCopyMarkdown()
                      }}
                    >
                      {copied ? 'Copied!' : 'Copy Markdown'}
                    </button>
                  </div>
                )}
              </div>
              <button
                type="button"
                className="drawer-close"
                onClick={onClose}
                aria-label="Close drawer (Escape)"
              >
                &#x2715;
              </button>
            </div>
          </header>

          <nav className="drawer-tabs" role="tablist" aria-label="CVE detail sections">
            {TABS.map(tab => (
              <ControlTooltip key={tab.id} text={tab.title} trigger="hover-focus">
                <button
                  type="button"
                  role="tab"
                  id={`drawer-tab-${tab.id}`}
                  className={`drawer-tab mono${activeTab === tab.id ? ' drawer-tab-active' : ''}`}
                  aria-selected={activeTab === tab.id}
                  aria-controls={`drawer-panel-${tab.id}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              </ControlTooltip>
            ))}
          </nav>
        </div>

        <div className="drawer-body-wrap">
          {showBlockingLoadingOverlay && (
            <div className="drawer-loading-overlay" aria-live="polite" aria-busy="true">
              <div className="drawer-loading-bar" role="progressbar" aria-label="Loading CVE details" />
              <p className="drawer-loading-text mono">Loading CVE details…</p>
            </div>
          )}

          {error && !hasPreviewContent && (
            <div className="drawer-error-overlay" role="alert">
              <p className="drawer-error-text mono">{error.message}</p>
              {error.requestId && (
                <p className="drawer-error-ref mono">
                  <a href={ingestLogUrl({ level: 'ERROR', requestId: error.requestId })}>
                    ref: {error.requestId}
                  </a>
                </p>
              )}
              {onRetry && (
                <button type="button" className="drawer-risk-profile-cta-btn mono" onClick={onRetry}>
                  Retry
                </button>
              )}
            </div>
          )}

          {error && hasPreviewContent && (
            <div className="drawer-error-banner mono" role="alert">
              <span>
                Failed to load full details: {error.message}
                {error.requestId && (
                  <>
                    {' '}
                    (<a href={ingestLogUrl({ level: 'ERROR', requestId: error.requestId })}>
                      ref: {error.requestId}
                    </a>)
                  </>
                )}
              </span>
              {onRetry && (
                <button type="button" className="drawer-risk-profile-cta-btn mono" onClick={onRetry}>
                  Retry
                </button>
              )}
            </div>
          )}

        <div
          className="drawer-tab-panel"
          role="tabpanel"
          id={`drawer-panel-${activeTab}`}
          aria-labelledby={`drawer-tab-${activeTab}`}
        >
          {activeTab === 'overview' && (
            <TabOverview
              cve={cve}
              riskScore={displayRiskScore}
              riskLoading={riskLoading}
              riskError={riskError}
              onOpenProfile={assetCtx?.openProfileFlow}
              momentumData={momentumData}
              products={products}
              cwes={cwes}
              capecIds={capecIds}
              urls={urls}
              sentences={sentences}
              sentencesLoading={sentencesLoading}
              epssHistory={epssHistory}
              epssLoading={epssLoading}
              epssSparklineRef={epssSparklineRef}
            />
          )}
          {activeTab === 'intel' && (
            <DrawerTabErrorBoundary>
            <TabIntel
              techniques={techniques}
              publicExploits={cve.public_exploits}
              exploitProvenance={cve.exploit_provenance}
              greynoiseConfigured={cve.greynoise_configured}
              greynoiseScans={greynoiseScans}
              greynoiseLoading={greynoiseLoading}
              greynoiseLoaded={greynoiseLoaded}
              greynoiseQuota={greynoiseQuota}
              onLoadGreynoise={loadGreynoiseScans}
              otxPulses={cve.otx_pulses}
              otxConfigured={cve.otx_configured}
              cve={cve}
              loading={loading}
              onInvestigateIp={
                investigation
                  ? (ip, cveCtx) => investigation.pivotToIoc(ip, {
                      type: 'cve',
                      id: cveCtx.cve_id,
                      title: cveCtx.cve_id,
                      description: (cveCtx.summary || '').slice(0, 80),
                    })
                  : undefined
              }
              onInvestigatePulse={investigation?.pivotToOtxPulse ? (pulse, cveCtx) => investigation.pivotToOtxPulse(pulse, cveCtx) : undefined}
              onInvestigateCampaign={
                investigation?.pivotToCampaign
                  ? (item, cveCtx) => investigation.pivotToCampaign(item, cveCtx)
                  : undefined
              }
              onOpenForgeTechnique={
                investigation?.pivotToTechnique
                  ? (techniqueId, name) => investigation.pivotToTechnique(techniqueId, name, {
                      type: 'cve',
                      id: cve.cve_id,
                      title: cve.cve_id,
                      description: (cve.summary || '').slice(0, 80),
                    })
                  : undefined
              }
              pivotNotice={investigation?.pivotNotice}
              correlation={correlation}
              correlationLoading={correlationLoading}
              onSelectCorrelatedCve={handleSelectRelated}
              onRequestSuppressCorrelation={handleRequestSuppressCorrelation}
              onConfirmCorrelation={handleConfirmCorrelation}
              correlationFeedback={correlationFeedback}
              suppressions={correlationSuppressions}
              onRestoreSuppression={handleRestoreSuppression}
            />
            </DrawerTabErrorBoundary>
          )}
          {activeTab === 'detect' && (
            <TabDetect
              detection={detection}
              loading={detectionLoading}
              error={detectionError}
              onRetry={() => {
                detectionFetchedRef.current = true
                const cleanup = loadDetection()
                detectionCancelRef.current = cleanup ?? null
              }}
            />
          )}
          {activeTab === 'related' && (
            <TabRelated
              related={related}
              relatedMethod={relatedMethod}
              relatedNews={relatedNews}
              loading={relatedLoading}
              onSelectRelated={handleSelectRelated}
            />
          )}
        </div>
        </div>
      </aside>

      <PdfExportModal
        open={pdfModalOpen}
        title={`PDF report — ${cve.cve_id}`}
        busy={pdfBusy}
        busyLabel="Generating PDF report…"
        error={pdfError}
        onConfirm={handlePdfConfirm}
        onCancel={() => {
          if (!pdfBusy) {
            setPdfModalOpen(false)
            setPdfError(null)
          }
        }}
      />

      <CorrelationSuppressModal
        open={!!suppressModal}
        body={suppressModal?.body}
        cveId={cve?.cve_id}
        peerCve={suppressModal?.peerCve}
        onCancel={() => !suppressSubmitting && setSuppressModal(null)}
        onConfirm={handleConfirmSuppress}
        submitting={suppressSubmitting}
      />
    </>
  )
}
