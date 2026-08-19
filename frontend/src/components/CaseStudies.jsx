import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ATLAS_VIEWS } from '../utils/shellUrlState.js'
import { Tabs, TabsList, TabsTrigger } from './ui/index.js'
import HeadlinesPanel from './advisories/HeadlinesPanel.jsx'
import AdvisoriesPanel from './advisories/AdvisoriesPanel.jsx'
import AtlasPanel from './advisories/AtlasPanel.jsx'
import './CaseStudies.css'

const SUB_NAV = [
  { id: 'headlines', label: 'HEADLINES' },
  { id: 'advisories', label: 'ADVISORIES' },
  { id: 'atlas', label: 'ATLAS' },
]

export default function CaseStudies({ initialSearch = '', onClearFilter, onOpenCve }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const viewParam = searchParams.get('view')
  const atlasView = ATLAS_VIEWS.has(viewParam) ? viewParam : 'headlines'

  const [search, setSearch] = useState(initialSearch)
  const [debounced, setDebounced] = useState(initialSearch)

  useEffect(() => {
    setSearch(initialSearch)
    setDebounced(initialSearch)
  }, [initialSearch])

  useEffect(() => {
    const id = setTimeout(() => setDebounced(search), 400)
    return () => clearTimeout(id)
  }, [search])

  function onAtlasViewChange(view) {
    if (!ATLAS_VIEWS.has(view)) return
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('tab', 'atlas')
      next.set('view', view)
      return next
    })
  }

  return (
    <div className="case-studies" role="region" aria-label="Advisories and intelligence">
      <header className="cs-hero">
        <p className="cs-hero-kicker mono">SECURITY CONTEXT</p>
        <h1 className="cs-hero-title">Advisories &amp; Intel</h1>
        <p className="cs-hero-sub">
          Headline security news, structured vendor advisories with durable CVE links, and MITRE
          ATLAS case studies — separate lanes, shared CVE spine.
        </p>
      </header>

      <Tabs value={atlasView} onValueChange={onAtlasViewChange} className="cs-subnav-wrap">
        <TabsList className="cs-subnav mono" aria-label="Advisories and intel views">
          {SUB_NAV.map(item => (
            <TabsTrigger key={item.id} value={item.id} className="cs-subnav-tab">
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div hidden={atlasView !== 'headlines'}>
        <HeadlinesPanel
          initialSearch={initialSearch}
          onClearFilter={onClearFilter}
          onOpenCve={onOpenCve}
          search={search}
          debounced={debounced}
          onSearchChange={setSearch}
        />
      </div>
      <div hidden={atlasView !== 'advisories'}>
        <AdvisoriesPanel onOpenCve={onOpenCve} />
      </div>
      <div hidden={atlasView !== 'atlas'}>
        <AtlasPanel onOpenCve={onOpenCve} debounced={debounced} />
      </div>
    </div>
  )
}
