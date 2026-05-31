import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import StatsRow from './components/StatsRow.jsx'
import CVEFeed from './components/CVEFeed.jsx'
import Sidebar from './components/Sidebar.jsx'
import IOCLookup from './components/IOCLookup.jsx'
import { fetchStats } from './api.js'

const DEFAULT_FILTERS = {
  severity: null,
  kev_only: false,
  poc_only: false,
  epss_min: null,
  search: '',
  stack: '',
}

export default function App() {
  const [activeTab, setActiveTab] = useState('feed')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [stats, setStats] = useState(null)
  const [selectedCVE, setSelectedCVE] = useState(null)

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => {})
  }, [])

  const handleBrief = useCallback((stack) => {
    setFilters(prev => ({ ...prev, stack }))
    setActiveTab('feed')
  }, [])

  const handleFiltersChange = useCallback((next) => {
    setFilters(prev => ({ ...prev, ...next }))
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
        <div className="footer-right">
          All times UTC &mdash; not a substitute for professional security advice
        </div>
      </footer>
    </div>
  )
}
