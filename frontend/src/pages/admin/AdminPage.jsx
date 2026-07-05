import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { adminApi, getAdminRequestId } from '../../api.js'
import { getAdminMode, setAdminMode } from '../../utils/adminMode.js'
import { getDisplayPrefs } from '../../utils/displayPrefs.js'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import StatusBar from './StatusBar.jsx'
import Sidebar from './Sidebar.jsx'
import ConfirmModal from './shared/ConfirmModal.jsx'
import ErrorBoundary from './shared/ErrorBoundary.jsx'
import { useToast, ToastArea } from './shared/Toast.jsx'
import { OperationProvider, OperationStrip, useOperations } from './shared/OperationTracker.jsx'
import { ANALYST_NAV } from './constants.js'
import OverviewPage from './OverviewPage.jsx'
import BackupsPage from './BackupsPage.jsx'
import StoragePage from './StoragePage.jsx'
import DatabasePage from './DatabasePage.jsx'
import WatchlistPage from './WatchlistPage.jsx'
import ApiKeysPage from './ApiKeysPage.jsx'
import SchedulerPage from './SchedulerPage.jsx'
import WebhooksPage from './WebhooksPage.jsx'
import AlertsPage from './AlertsPage.jsx'
import SecurityPage from './SecurityPage.jsx'
import FeedHealthPage from './FeedHealthPage.jsx'
import IngestLogPage from './IngestLogPage.jsx'
import AuditLogPage from './AuditLogPage.jsx'
import DisplayPage from './DisplayPage.jsx'
import ComingSoonPage from './ComingSoonPage.jsx'
import SessionsPage from './SessionsPage.jsx'
import RateLimitPage from './RateLimitPage.jsx'
import UserMenu from '../../components/UserMenu.jsx'
import { loadJobAcks, markAllJobErrorsRead, filterUnacknowledgedErrors } from './adminJobAck.js'
import { jobErrorsFromSystem } from './shared/JobErrorsPanel.jsx'
import '../AdminPage.css'

const ANALYST_PAGE_IDS = new Set(ANALYST_NAV.flatMap(section => section.items.map(i => i.id)))
const VALID_ADMIN_PAGES = new Set([
  'overview', 'backups', 'storage', 'database', 'watchlist', 'apikeys', 'scheduler',
  'webhooks', 'alerts', 'security', 'feedhealth', 'ingestlog', 'auditlog', 'display',
  'sessions', 'ratelimit',
])

function AdminPageBody({ toast, toasts, dismissToast }) {
  const { runAction } = useOperations()
  const [searchParams] = useSearchParams()
  const [page, setPageRaw] = useState('overview')
  // Tracks which sub-pages have ever been visited, so we only mount (and let
  // fire their data-loading effects) pages the user has actually opened,
  // instead of all of them at once on every admin-panel open.
  const [visitedPages, setVisitedPages] = useState(() => new Set(['overview']))
  const setPage = useCallback((id) => {
    setVisitedPages(prev => (prev.has(id) ? prev : new Set(prev).add(id)))
    setPageRaw(id)
    setSidebarOpen(false)
  }, [])
  const [mode, setModeState] = useState(getAdminMode)
  const [system, setSystem] = useState(null)
  const [ingestErrorCount, setIngestErrorCount] = useState(0)
  const [confirmOperatorSwitch, setConfirmOperatorSwitch] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [jobAcks, setJobAcks] = useState(() => loadJobAcks())
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pollRef = useRef(null)

  const urlFilters = useMemo(() => ({
    ingest: {
      level: searchParams.get('level') || '',
      category: searchParams.get('category') || '',
      logger: searchParams.get('logger') || '',
      requestId: searchParams.get('request_id') || '',
    },
    audit: {
      actionPrefix: searchParams.get('action_prefix') || '',
      q: searchParams.get('q') || '',
    },
    feedSource: searchParams.get('source') || '',
  }), [searchParams])

  async function loadSystem() {
    try {
      const res = await adminApi.get('/system')
      if (!res.ok) {
        const requestId = getAdminRequestId(res)
        toast({
          message: `System status unavailable (HTTP ${res.status})`,
          variant: 'warning',
          actions: [{ label: 'View application log', href: ingestLogUrl({ level: 'ERROR', requestId }) }],
          requestId,
        })
        return
      }
      const data = await res.json()
      setSystem(data); setLastUpdated(Date.now())
    } catch (err) {
      toast({
        message: err?.message || 'Failed to load system status',
        variant: 'warning',
        actions: [{ label: 'View application log', href: ingestLogUrl({ level: 'ERROR', requestId: err?.requestId }) }],
        requestId: err?.requestId,
      })
    }
  }

  useEffect(() => {
    loadSystem()
  }, [])

  useEffect(() => {
    const requested = searchParams.get('p')
    if (requested && VALID_ADMIN_PAGES.has(requested)) {
      setPage(requested)
    }
  }, [searchParams, setPage])

  useEffect(() => {
    function setupPolling() {
      clearInterval(pollRef.current)
      const seconds = getDisplayPrefs().pollIntervalSeconds || 30
      pollRef.current = setInterval(loadSystem, seconds * 1000)
    }
    setupPolling()
    window.addEventListener('briefr-display-prefs-changed', setupPolling)
    return () => {
      clearInterval(pollRef.current)
      window.removeEventListener('briefr-display-prefs-changed', setupPolling)
    }
  }, [])

  function setMode(next) {
    setModeState(next)
    setAdminMode(next)
    if (next === 'analyst' && !ANALYST_PAGE_IDS.has(page)) setPage('overview')
  }

  function getOperatorAck() {
    try { return sessionStorage.getItem('briefr-operator-ack') === '1' } catch { return false }
  }
  function setOperatorAck() {
    try { sessionStorage.setItem('briefr-operator-ack', '1') } catch { /* unavailable */ }
  }

  function handleModeChange(next) {
    if (next === mode) return
    if (next === 'operator' && !getOperatorAck()) { setConfirmOperatorSwitch(true); return }
    setMode(next)
  }

  async function handleRunIngest() {
    await runAction({
      id: 'full-ingest',
      label: 'Refreshing all sources',
      kind: 'ingest',
      successMessage: 'Full ingest started — sources will update as jobs complete',
      execute: async () => {
        const res = await fetch('/api/refresh', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          signal: AbortSignal.timeout(60_000),
        })
        const requestId = getAdminRequestId(res)
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          const err = new Error(body.detail || 'Failed to start full ingest')
          err.requestId = requestId
          throw err
        }
        return { requestId }
      },
    })
  }

  async function handleRestart() {
    try {
      await adminApi.post('/restart', { confirm_text: 'restart' })
      toast('Backend is shutting down gracefully…', true)
    } catch (e) { toast(String(e.message), false) }
  }

  async function handleDrainRestart() {
    try {
      await adminApi.post('/restart', { drain: true, confirm_text: 'restart' })
      toast('Drain initiated — backend will shut down gracefully when jobs complete', true)
    } catch (e) { toast(String(e.message), false) }
  }

  const isComingSoon = page.startsWith('coming-')

  const unackJobErrorCount = useMemo(
    () => filterUnacknowledgedErrors(jobErrorsFromSystem(system), jobAcks).length,
    [system, jobAcks],
  )

  function handleMarkJobErrorsRead(errors) {
    setJobAcks(markAllJobErrorsRead(errors))
    toast('Marked job errors as read', true)
  }

  const pages = {
    overview: (
      <OverviewPage
        system={system}
        toast={toast}
        mode={mode}
        jobAcks={jobAcks}
        onMarkJobErrorsRead={handleMarkJobErrorsRead}
      />
    ),
    backups: <BackupsPage toast={toast} system={system} />,
    storage: <StoragePage toast={toast} />,
    database: <DatabasePage toast={toast} active={page === 'database'} />,
    watchlist: <WatchlistPage toast={toast} mode={mode} />,
    apikeys: <ApiKeysPage toast={toast} />,
    scheduler: <SchedulerPage toast={toast} system={system} onRunIngest={handleRunIngest} onRestart={handleRestart} onDrainRestart={handleDrainRestart} onRefreshSystem={loadSystem} />,
    webhooks: <WebhooksPage toast={toast} />,
    alerts: <AlertsPage toast={toast} />,
    security: <SecurityPage />,
    feedhealth: <FeedHealthPage system={system} toast={toast} mode={mode} onReload={loadSystem} highlightSource={urlFilters.feedSource} />,
    ingestlog: <IngestLogPage toast={toast} onErrorCountChange={setIngestErrorCount} active={page === 'ingestlog'} urlFilters={urlFilters.ingest} />,
    auditlog: <AuditLogPage toast={toast} urlFilters={urlFilters.audit} />,
    display: <DisplayPage />,
    sessions: <SessionsPage toast={toast} />,
    ratelimit: <RateLimitPage toast={toast} />,
  }

  return (
    <div className={`admin-root admin-root--${mode}`}>
      {confirmOperatorSwitch && (
        <ConfirmModal
          title="Switch to Operator view?"
          message="Operator view exposes destructive actions: restart, full ingest, purge, and config changes. Use it only when you need to manage the system, not for everyday CVE triage."
          confirmWord={undefined}
          onConfirm={() => { setOperatorAck(); setConfirmOperatorSwitch(false); setMode('operator') }}
          onCancel={() => setConfirmOperatorSwitch(false)}
        />
      )}
      <StatusBar
        system={system}
        onRunIngest={handleRunIngest}
        refreshInProgress={system?.refresh_in_progress || false}
        mode={mode}
        setMode={handleModeChange}
        lastUpdated={lastUpdated}
        userMenu={<UserMenu className="user-menu-wrap--admin" />}
        onToggleSidebar={() => setSidebarOpen(v => !v)}
        sidebarOpen={sidebarOpen}
      />
      <OperationStrip />
      <div className="admin-body">
        {sidebarOpen && (
          <button
            type="button"
            className="admin-sidebar-backdrop"
            aria-label="Close navigation"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        <Sidebar
          activePage={page}
          setPage={setPage}
          system={system}
          ingestErrorCount={ingestErrorCount}
          unackJobErrorCount={unackJobErrorCount}
          mode={mode}
          setMode={handleModeChange}
          open={sidebarOpen}
        />
        <div className="admin-content">
          {isComingSoon ? (
            <ComingSoonPage pageId={page} setPage={setPage} />
          ) : (
            Object.entries(pages)
              .filter(([id]) => visitedPages.has(id))
              .map(([id, content]) => (
                <div key={id} hidden={page !== id}>
                  <ErrorBoundary>{content}</ErrorBoundary>
                </div>
              ))
          )}
        </div>
      </div>
      <ToastArea toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

export default function AdminPage() {
  const { toasts, show: toast, dismiss: dismissToast } = useToast()
  return (
    <OperationProvider toast={toast}>
      <AdminPageBody toast={toast} toasts={toasts} dismissToast={dismissToast} />
    </OperationProvider>
  )
}
