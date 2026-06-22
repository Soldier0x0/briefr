import { useState, useEffect, useRef } from 'react'
import { adminApi, getAdminKey, setAdminKey } from '../../api.js'
import { getAdminMode, setAdminMode } from '../../utils/adminMode.js'
import { getDisplayPrefs } from '../../utils/displayPrefs.js'
import AdminPage_KeyModal from '../AdminPage_KeyModal.jsx'
import StatusBar from './StatusBar.jsx'
import Sidebar from './Sidebar.jsx'
import ConfirmModal from './shared/ConfirmModal.jsx'
import ErrorBoundary from './shared/ErrorBoundary.jsx'
import { useToast, ToastArea } from './shared/Toast.jsx'
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
import '../AdminPage.css'

const ANALYST_PAGE_IDS = new Set(ANALYST_NAV.flatMap(section => section.items.map(i => i.id)))

export default function AdminPage() {
  const [page, setPageRaw] = useState('overview')
  // Tracks which sub-pages have ever been visited, so we only mount (and let
  // fire their data-loading effects) pages the user has actually opened,
  // instead of all of them at once on every admin-panel open.
  const [visitedPages, setVisitedPages] = useState(() => new Set(['overview']))
  function setPage(id) {
    setVisitedPages(prev => (prev.has(id) ? prev : new Set(prev).add(id)))
    setPageRaw(id)
  }
  const [mode, setModeState] = useState(getAdminMode)
  const [system, setSystem] = useState(null)
  const [keyModalOpen, setKeyModalOpen] = useState(false)
  const [modalError, setModalError] = useState('')
  const [authed, setAuthed] = useState(false)
  const [ingestErrorCount, setIngestErrorCount] = useState(0)
  const [confirmOperatorSwitch, setConfirmOperatorSwitch] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const { toasts, show: toast, dismiss: dismissToast } = useToast()
  const pollRef = useRef(null)

  async function loadSystem() {
    try {
      const res = await adminApi.get('/system')
      if (res.status === 401) {
        setAuthed(false); setKeyModalOpen(true); return
      }
      if (!res.ok) return
      const data = await res.json()
      setSystem(data); setAuthed(true); setKeyModalOpen(false); setModalError(''); setLastUpdated(Date.now())
    } catch (e) {
      if (e?.status === 401) { setAuthed(false); setKeyModalOpen(true) }
    }
  }

  async function checkKeyRequired() {
    try {
      const res = await adminApi.get('/security')
      if (res.status === 401) { setKeyModalOpen(true); return }
      if (!res.ok) { await loadSystem(); return }
      const data = await res.json()
      if (!data.admin_key_set) { setAuthed(true); await loadSystem() }
      else if (!getAdminKey()) { setKeyModalOpen(true) }
      else { await loadSystem() }
    } catch (e) {
      if (e?.status === 401) setKeyModalOpen(true)
      else await loadSystem()
    }
  }

  useEffect(() => {
    checkKeyRequired()
  }, [])

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

  function handleKeySubmit(key) {
    setAdminKey(key)
    setModalError('')
    loadSystem().then(() => {
      if (!authed && !getAdminKey()) setModalError('Invalid key')
    })
  }

  async function handleRunIngest() {
    try {
      const res = await fetch('/api/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-BRIEFR-Admin-Key': getAdminKey() },
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      toast('Full ingest started', true)
    } catch (e) { toast(String(e.message), false) }
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

  const pages = {
    overview: <OverviewPage system={system} toast={toast} mode={mode} />,
    backups: <BackupsPage toast={toast} system={system} />,
    storage: <StoragePage toast={toast} />,
    database: <DatabasePage toast={toast} active={page === 'database'} />,
    watchlist: <WatchlistPage toast={toast} mode={mode} />,
    apikeys: <ApiKeysPage toast={toast} />,
    scheduler: <SchedulerPage toast={toast} system={system} />,
    webhooks: <WebhooksPage toast={toast} />,
    alerts: <AlertsPage toast={toast} />,
    security: <SecurityPage toast={toast} />,
    feedhealth: <FeedHealthPage system={system} toast={toast} mode={mode} onReload={loadSystem} />,
    ingestlog: <IngestLogPage toast={toast} onErrorCountChange={setIngestErrorCount} active={page === 'ingestlog'} />,
    auditlog: <AuditLogPage toast={toast} />,
    display: <DisplayPage />,
  }

  return (
    <div className="admin-root">
      {keyModalOpen && (
        <AdminPage_KeyModal onSubmit={handleKeySubmit} error={modalError} />
      )}
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
        onRestart={handleRestart}
        onDrainRestart={handleDrainRestart}
        refreshInProgress={system?.refresh_in_progress || false}
        mode={mode}
        setMode={handleModeChange}
        lastUpdated={lastUpdated}
      />
      <div className="admin-body">
        <Sidebar activePage={page} setPage={setPage} system={system} ingestErrorCount={ingestErrorCount} mode={mode} setMode={handleModeChange} />
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
