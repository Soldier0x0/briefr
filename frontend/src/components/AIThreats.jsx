import { useEffect, useState, useMemo } from 'react'
import { fetchAtlasCaseStudies, fetchAtlasTechniques } from '../api.js'
import { useInvestigationOptional } from '../context/InvestigationContext.jsx'
import './AIThreats.css'

function oneLineDescription(text) {
  if (!text) return ''
  const line = text.replace(/\s+/g, ' ').trim()
  return line.length > 140 ? `${line.slice(0, 137)}...` : line
}

function matchesActor(text, actorFilter) {
  if (!actorFilter || !text) return true
  return text.toLowerCase().includes(actorFilter.toLowerCase())
}

export default function AIThreats({ actorFilter, onClearActorFilter }) {
  const investigation = useInvestigationOptional()
  const [tacticGroups, setTacticGroups] = useState([])
  const [caseStudies, setCaseStudies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [openTactics, setOpenTactics] = useState({})
  const [expandedStudy, setExpandedStudy] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([fetchAtlasTechniques(), fetchAtlasCaseStudies(30)])
      .then(([techRes, casesRes]) => {
        if (cancelled) return
        const groups = techRes.data || []
        setTacticGroups(groups)
        setCaseStudies(casesRes.data || [])
        const initialOpen = {}
        groups.slice(0, 3).forEach(g => {
          initialOpen[g.tactic_id || g.tactic_name] = true
        })
        setOpenTactics(initialOpen)
      })
      .catch(err => {
        if (!cancelled) setError(err.message || 'Failed to load ATLAS data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  function toggleTactic(key) {
    setOpenTactics(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const filteredCaseStudies = useMemo(() => {
    if (!actorFilter) return caseStudies
    return caseStudies.filter(study => {
      const hay = `${study.name} ${study.target} ${study.summary}`.toLowerCase()
      return hay.includes(actorFilter.toLowerCase())
    })
  }, [caseStudies, actorFilter])

  const filteredTacticGroups = useMemo(() => {
    if (!actorFilter) return tacticGroups
    const studyTechIds = new Set()
    filteredCaseStudies.forEach(s => {
      ;(s.techniques || []).forEach(tid => studyTechIds.add(tid))
      ;(s.technique_details || []).forEach(t => studyTechIds.add(t.technique_id))
    })
    return tacticGroups
      .map(group => ({
        ...group,
        techniques: group.techniques.filter(
          t => studyTechIds.has(t.technique_id) || matchesActor(t.name, actorFilter),
        ),
      }))
      .filter(g => g.techniques.length > 0)
  }, [tacticGroups, filteredCaseStudies, actorFilter])

  function handleCVEClick(cveId, studyName, e) {
    e.preventDefault()
    e.stopPropagation()
    if (investigation) {
      investigation.pivotToCveFromAtlas(cveId, studyName)
    }
  }

  return (
    <div className="ai-threats" role="region" aria-label="AI and ML threat intelligence">
      <header className="ai-hero">
        <p className="ai-hero-kicker mono">AI-SPECIFIC THREAT INTELLIGENCE</p>
        <h1 className="ai-hero-title">AI and ML Threat Landscape</h1>
        <p className="ai-hero-sub">
          Adversarial techniques and real-world case studies targeting machine learning
          systems — separate from CVE-centric Enterprise ATT&amp;CK coverage.
        </p>
        <a
          className="ai-atlas-badge mono"
          href="https://atlas.mitre.org/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Powered by MITRE ATLAS &rarr;
        </a>
      </header>

      {loading && (
        <p className="ai-state mono" aria-live="polite">// Loading ATLAS intelligence...</p>
      )}
      {error && (
        <p className="ai-state ai-state-error" role="alert">{error}</p>
      )}

      {actorFilter && (
        <div className="ai-actor-filter-banner" role="status">
          <span>
            Filtered to threat context matching <strong>{actorFilter}</strong>
          </span>
          {onClearActorFilter && (
            <button type="button" className="ai-actor-filter-clear mono" onClick={onClearActorFilter}>
              Clear filter
            </button>
          )}
        </div>
      )}

      {!loading && !error && (
        <div className="ai-layout">
          <section className="ai-col-techniques" aria-labelledby="ai-techniques-heading">
            <h2 id="ai-techniques-heading" className="ai-col-heading mono">
              ATLAS TECHNIQUES BY TACTIC
            </h2>
            <p className="ai-col-note">
              MITRE ATLAS adversarial ML techniques (not Enterprise ATT&amp;CK).
            </p>
            <div className="ai-tactic-list">
              {(actorFilter ? filteredTacticGroups : tacticGroups).map(group => {
                const key = group.tactic_id || group.tactic_name
                const open = !!openTactics[key]
                return (
                  <div key={key} className="ai-tactic-block">
                    <button
                      type="button"
                      className="ai-tactic-toggle mono"
                      onClick={() => toggleTactic(key)}
                      aria-expanded={open}
                    >
                      <span className="ai-tactic-toggle-label">{group.tactic_name}</span>
                      <span className="ai-tactic-count">{group.techniques.length}</span>
                      <span className="ai-tactic-chevron" aria-hidden="true">{open ? '−' : '+'}</span>
                    </button>
                    {open && (
                      <ul className="ai-technique-list">
                        {group.techniques.map(tech => (
                          <li key={tech.technique_id} className="ai-technique-item">
                            <div className="ai-technique-top">
                              <a
                                className="ai-technique-id mono"
                                href={tech.url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                {tech.technique_id}
                              </a>
                            </div>
                            <p className="ai-technique-name">{tech.name}</p>
                            <p className="ai-technique-desc">
                              {oneLineDescription(tech.description)}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )
              })}
            </div>
          </section>

          <section className="ai-col-cases" aria-labelledby="ai-cases-heading">
            <h2 id="ai-cases-heading" className="ai-col-heading mono">
              CASE STUDIES
            </h2>
            <p className="ai-col-note">Documented adversarial ML incidents and exercises.</p>
            <div className="ai-case-list">
              {(actorFilter ? filteredCaseStudies : caseStudies).map(study => {
                const expanded = expandedStudy === study.study_id
                const badges = study.technique_details || []
                return (
                  <article
                    key={study.study_id}
                    className={`ai-case-card${expanded ? ' ai-case-card-expanded' : ''}`}
                  >
                    <button
                      type="button"
                      className="ai-case-card-btn"
                      onClick={() => setExpandedStudy(expanded ? null : study.study_id)}
                      aria-expanded={expanded}
                    >
                      <h3 className="ai-case-title">{study.name}</h3>
                      <div className="ai-case-meta mono">
                        <span>{study.target}</span>
                        {study.date && <span className="ai-case-date">{study.date}</span>}
                      </div>
                      {!expanded && (
                        <p className="ai-case-summary-preview">{study.summary}</p>
                      )}
                      <div className="ai-case-badges">
                        {badges.slice(0, 6).map(t => (
                          <span key={t.technique_id} className="ai-tech-badge mono">
                            {t.technique_id}
                          </span>
                        ))}
                        {badges.length > 6 && (
                          <span className="ai-tech-badge mono">+{badges.length - 6}</span>
                        )}
                      </div>
                    </button>
                    {expanded && (
                      <div className="ai-case-expanded">
                        <p className="ai-case-summary-full">
                          {study.summary_full || study.summary}
                        </p>
                        {badges.length > 0 && (
                          <div className="ai-case-techniques-expanded">
                            <span className="ai-case-expanded-label mono">Mapped techniques</span>
                            <div className="ai-case-badges">
                              {badges.map(t => (
                                <a
                                  key={t.technique_id}
                                  className="ai-tech-badge ai-tech-badge-link mono"
                                  href={t.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={e => e.stopPropagation()}
                                >
                                  {t.technique_id}
                                </a>
                              ))}
                            </div>
                          </div>
                        )}
                        {study.cve_ids?.length > 0 && (
                          <div className="ai-case-cves">
                            <span className="ai-case-expanded-label mono">Related CVEs</span>
                            <div className="ai-cve-links">
                              {study.cve_ids.map(cveId => (
                                <button
                                  key={cveId}
                                  type="button"
                                  className="ai-cve-link mono"
                                  onClick={e => handleCVEClick(cveId, study.name, e)}
                                >
                                  {cveId}
                                </button>
                              ))}
                            </div>
                            <p className="ai-cve-hint mono">
                              Opens in BRIEF feed drawer
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                )
              })}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
