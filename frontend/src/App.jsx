import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import StatsRow from './components/StatsRow.jsx'
import CVEFeed from './components/CVEFeed.jsx'
import Sidebar from './components/Sidebar.jsx'
import IOCLookup from './components/IOCLookup.jsx'
import DetailDrawer from './components/DetailDrawer.jsx'
import DigestModal from './components/DigestModal.jsx'
import { fetchStats } from './api.js'

const DEFAULT_FILTERS = {
  severity: null,
  kev_only: false,
  poc_only: false,
  epss_min: null,
  search: '',
  stack: '',
}

// F key cycles: all → kev → critical → poc → all
function cycleFilter(filters) {
  if (!filters.kev_only && !filters.poc_only && !filters.severity) {
    return { ...filters, kev_only: true, poc_only: false, severity: null }
  }
  if (filters.kev_only) {
    return { ...filters, kev_only: false, poc_only: false, severity: 'CRITICAL' }
  }
  if (filters.severity === 'CRITICAL') {
    return { ...filters, kev_only: false, poc_only: true, severity: null }
  }
  return { ...filters, kev_only: false, poc_only: false, severity: null }
}

export default function App() {
  const [activeTab, setActiveTab]               = useState('feed')
  const [filters, setFilters]                   = useState(DEFAULT_FILTERS)
  const [stats, setStats]                       = useState(null)
  const [selectedCVE, setSelectedCVE]           = useState(null)
  const [digestOpen, setDigestOpen]             = useState(false)
  const [digestCVEs, setDigestCVEs]             = useState([])
  const [searchFocusTrigger, setSearchFocusTrigger] = useState(0)

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {})
  }, [])

  // ── Keyboard shortcuts ────────────────────────────────────
  useEffect(() => {
    function handleKey(e) {
      // Escape: close drawer first, then modal
      if (e.key === 'Escape') {
        if (selectedCVE) { setSelectedCVE(null); return }
        if (digestOpen)  { setDigestOpen(false);  return }
        return
      }

      // Don't fire remaining shortcuts when user is typing
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      // / — focus CVE search input
      if (e.key === '/') {
        e.preventDefault()
        setSearchFocusTrigger(n => n + 1)
      }

      // F — cycle filter states
      if (e.key === 'f' || e.key === 'F') {
        setFilters(prev => cycleFilter(prev))
      }
    }

    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [selectedCVE, digestOpen])

  const handleBrief = useCallback((stack) => {
    setFilters(prev => ({ ...prev, stack }))
    setActiveTab('feed')
  }, [])

  const handleFiltersChange = useCallback((next) => {
    setFilters(prev => ({ ...prev, ...next }))
  }, [])

  const handleGenerateDigest = useCallback((cves) => {
    setDigestCVEs(cves)
    setDigestOpen(true)
  }, [])

  return (
    <div className="app">
      <Header activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="app-main">
        {activeTab === 'feed' && (
          <>
            <Hero onBrief={handleBrief} />
            <StatsRow stats={stats} />
            <div className="content-grid">
              <CVEFeed
                filters={filters}
                onFiltersChange={handleFiltersChange}
                onSelectCVE={setSelectedCVE}
                onGenerateDigest={handleGenerateDigest}
                searchFocusTrigger={searchFocusTrigger}
              />
              <Sidebar
                filters={filters}
                onFiltersChange={handleFiltersChange}
                stats={stats}
              />
            </div>
          </>
        )}

        {activeTab === 'ioc' && (
          <IOCLookup />
        )}
      </div>

      <footer className="app-footer" role="contentinfo">
        <div className="footer-left">
          <span>VEKTOR</span> // CVE intelligence platform // data from NVD, CISA, FIRST, OSV
        </div>
        <div className="footer-right mono" style={{ fontSize: '0.6875rem', color: 'var(--text3)' }}>
          Press <kbd>/</kbd> to search &nbsp;&middot;&nbsp; <kbd>F</kbd> to cycle filters &nbsp;&middot;&nbsp; <kbd>Esc</kbd> to close
        </div>
      </footer>

      {/* Detail drawer — rendered outside main to overlay everything */}
      <DetailDrawer
        cve={selectedCVE}
        onClose={() => setSelectedCVE(null)}
      />

      {/* Digest modal — absolute within .app (position:relative), no fixed */}
      {digestOpen && (
        <DigestModal
          cves={digestCVEs}
          filters={filters}
          onClose={() => setDigestOpen(false)}
        />
      )}
    </div>
  )
}
