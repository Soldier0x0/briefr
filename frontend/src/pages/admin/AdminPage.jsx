import { useState, useEffect, useRef } from 'react'
import { adminApi, getAdminKey, setAdminKey } from '../../api.js'
import AdminPage_KeyModal from '../AdminPage_KeyModal.jsx'
import StatusBar from './StatusBar.jsx'
import Sidebar from './Sidebar.jsx'
import ErrorBoundary from './shared/ErrorBoundary.jsx'
import { useToast, ToastArea } from './shared/Toast.jsx'
import OverviewPage from './OverviewPage.jsx'
import BackupsPage from './BackupsPage.jsx'
import StoragePage from './StoragePage.jsx'
import DatabasePage from './DatabasePage.jsx'
import WatchlistPage from './WatchlistPage.jsx'
import ApiKeysPage from './ApiKeysPage.jsx'
import SchedulerPage from './SchedulerPage.jsx'
import WebhooksPage from './WebhooksPage.jsx'
import SecurityPage from './SecurityPage.jsx'
import FeedHealthPage from './FeedHealthPage.jsx'
import IngestLogPage from './IngestLogPage.jsx'
import AuditLogPage from './AuditLogPage.jsx'
import ComingSoonPage from './ComingSoonPage.jsx'
import '../AdminPage.css'

export default function AdminPage() {
  const [page, setPage] = useState('overview')
  const [system, setSystem] = useState(null)
  const [keyModalOpen, setKeyModalOpen] = useState(false)
  const [modalError, setModalError] = useState('')
  const [authed, setAuthed] = useState(false)
  const [ingestErrorCount, setIngestErrorCount] = useState(0)
  const { toasts, show: toast } = useToast()
  const pollRef = useRef(null)

  async function loadSystem() {
    try {
      const res = await adminApi.get('/system')
      if (res.status === 401) {
        setAuthed(false); setKeyModalOpen(true); return
      }
      if (!res.ok) return
      const data = await res.json()
      setSystem(data); setAuthed(true); setKeyModalOpen(false); setModalError('')
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
    pollRef.current = setInterval(loadSystem, 30000)
    return () => clearInterval(pollRef.current)
  }, [])

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
    overview: <OverviewPage system={system} toast={toast} />,
    backups: <BackupsPage toast={toast} system={system} />,
    storage: <StoragePage toast={toast} />,
    database: <DatabasePage toast={toast} active={page === 'database'} />,
    watchlist: <WatchlistPage toast={toast} />,
    apikeys: <ApiKeysPage toast={toast} />,
    scheduler: <SchedulerPage toast={toast} system={system} />,
    webhooks: <WebhooksPage toast={toast} />,
    security: <SecurityPage toast={toast} />,
    feedhealth: <FeedHealthPage system={system} toast={toast} />,
    ingestlog: <IngestLogPage toast={toast} onErrorCountChange={setIngestErrorCount} active={page === 'ingestlog'} />,
    auditlog: <AuditLogPage toast={toast} />,
  }

  return (
    <div className="admin-root">
      {keyModalOpen && (
        <AdminPage_KeyModal onSubmit={handleKeySubmit} error={modalError} />
      )}
      <StatusBar
        system={system}
        onRunIngest={handleRunIngest}
        onRestart={handleRestart}
        onDrainRestart={handleDrainRestart}
        refreshInProgress={system?.refresh_in_progress || false}
      />
      <div className="admin-body">
        <Sidebar activePage={page} setPage={setPage} system={system} ingestErrorCount={ingestErrorCount} />
        <div className="admin-content">
          {isComingSoon ? (
            <ComingSoonPage pageId={page} setPage={setPage} />
          ) : (
            Object.entries(pages).map(([id, content]) => (
              <div key={id} hidden={page !== id}>
                <ErrorBoundary>{content}</ErrorBoundary>
              </div>
            ))
          )}
        </div>
      </div>
      <ToastArea toasts={toasts} />
    </div>
  )
}
