import { useState, useEffect, useCallback } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import StatsRow from './components/StatsRow.jsx'
import CVEFeed from './components/CVEFeed.jsx'
import Sidebar from './components/Sidebar.jsx'
import IOCLookup from './components/IOCLookup.jsx'
import DetailDrawer from './components/DetailDrawer.jsx'
import DigestModal from './components/DigestModal.jsx'
import AboutModal from './components/AboutModal.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import TermsPage from './pages/TermsPage.jsx'
import { fetchStats } from './api.js'

const DEFAULT_FILTERS = {
  severity: null,
  kev_only: false,
  poc_only: false,
  epss_min: null,
  search: '',
  stack: '',
}

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

function MainApp({ stats, filters, setFilters, selectedCVE, setSelectedCVE,
                   digestOpen, setDigestOpen, digestCVEs, setDigestCVEs,
                   searchFocusTrigger, setSearchFocusTrigger, aboutOpen, setAboutOpen }) {

  const handleBrief = useCallback((stack) => {
    setFilters(prev => ({ ...prev, stack }))
  }, [setFilters])

  const handleFiltersChange = useCallback((next) => {
    setFilters(prev => ({ ...prev, ...next }))
  }, [setFilters])

  const handleGenerateDigest = useCallback((cves) => {
    setDigestCVEs(cves)
    setDigestOpen(true)
  }, [setDigestCVEs, setDigestOpen])

  return (
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
        <Sidebar filters={filters} onFiltersChange={handleFiltersChange} stats={stats} />
      </div>
    </>
  )
}

export default function App() {
  const [activeTab, setActiveTab]               = useState('feed')
  const [filters, setFilters]                   = useState(DEFAULT_FILTERS)
  const [stats, setStats]                       = useState(null)
  const [selectedCVE, setSelectedCVE]           = useState(null)
  const [digestOpen, setDigestOpen]             = useState(false)
  const [digestCVEs, setDigestCVEs]             = useState([])
  const [searchFocusTrigger, setSearchFocusTrigger] = useState(0)
  const [aboutOpen, setAboutOpen]               = useState(false)

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {})
  }, [])

  // ── Global keyboard shortcuts ─────────────────────────────
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') {
        if (aboutOpen)    { setAboutOpen(false);  return }
        if (selectedCVE)  { setSelectedCVE(null); return }
        if (digestOpen)   { setDigestOpen(false); return }
        return
      }
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === '/') { e.preventDefault(); setSearchFocusTrigger(n => n + 1) }
      if (e.key === 'f' || e.key === 'F') setFilters(cycleFilter)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [aboutOpen, selectedCVE, digestOpen])

  return (
    <div className="app">
      <Routes>
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms"   element={<TermsPage />} />
        <Route path="*" element={
          <>
            <Header
              activeTab={activeTab}
              onTabChange={setActiveTab}
              onAboutOpen={() => setAboutOpen(true)}
            />

            <div className="app-main">
              {activeTab === 'feed' && (
                <MainApp
                  stats={stats}
                  filters={filters}
                  setFilters={setFilters}
                  selectedCVE={selectedCVE}
                  setSelectedCVE={setSelectedCVE}
                  digestOpen={digestOpen}
                  setDigestOpen={setDigestOpen}
                  digestCVEs={digestCVEs}
                  setDigestCVEs={setDigestCVEs}
                  searchFocusTrigger={searchFocusTrigger}
                  setSearchFocusTrigger={setSearchFocusTrigger}
                  aboutOpen={aboutOpen}
                  setAboutOpen={setAboutOpen}
                />
              )}
              {activeTab === 'ioc' && <IOCLookup />}
            </div>

            <footer className="app-footer" role="contentinfo">
              <div className="footer-left">
                <span>VEKTOR</span> // CVE intelligence platform // data from NVD, CISA, FIRST, OSV
              </div>
              <div className="footer-right mono" style={{ fontSize: '0.6875rem', color: 'var(--text3)' }}>
                Press <kbd>/</kbd> to search &nbsp;&middot;&nbsp;
                <kbd>F</kbd> to cycle filters &nbsp;&middot;&nbsp;
                <kbd>Esc</kbd> to close
              </div>
            </footer>

            <DetailDrawer cve={selectedCVE} onClose={() => setSelectedCVE(null)} />

            {digestOpen && (
              <DigestModal cves={digestCVEs} filters={filters} onClose={() => setDigestOpen(false)} />
            )}

            {aboutOpen && (
              <AboutModal onClose={() => setAboutOpen(false)} />
            )}
          </>
        } />
      </Routes>
    </div>
  )
}
