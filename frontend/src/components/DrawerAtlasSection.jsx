import { cveMatchesDeclaredAi } from '../utils/aiAssets.js'
import { formatSectionHeading } from '../utils/sectionHeading.js'

function atlasTechniqueHref(tech) {
  if (tech?.url) return tech.url
  const id = tech?.technique_id || tech?.id
  if (!id) return null
  return `https://atlas.mitre.org/techniques/${String(id).toUpperCase()}/`
}

export default function DrawerAtlasSection({ cve }) {
  if (!cve?.has_ai_context) return null

  const techniques = Array.isArray(cve.atlas_techniques) ? cve.atlas_techniques : []
  const studies = Array.isArray(cve.atlas_case_studies) ? cve.atlas_case_studies : []
  const affectsDeclared = cveMatchesDeclaredAi(cve)

  return (
    <section className="drawer-section drawer-atlas-section" aria-labelledby="atlas-heading">
      <div className="drawer-atlas-head">
        <h3 id="atlas-heading" className="drawer-atlas-label mono">
          {formatSectionHeading('// AI/ML THREAT CONTEXT')}
        </h3>
        <a
          className="drawer-atlas-badge mono"
          href="https://atlas.mitre.org/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Powered by MITRE ATLAS
        </a>
      </div>

      {affectsDeclared && (
        <p className="drawer-atlas-profile-warn mono">
          This CVE may affect your declared AI/ML systems
        </p>
      )}

      {techniques.length === 0 ? (
        <p className="drawer-intel-empty mono">// No ATLAS techniques linked for this CVE</p>
      ) : (
        <div className="atlas-techniques" role="list" aria-label="Relevant ATLAS techniques">
          {techniques.map(tech => {
            const tid = tech.technique_id || tech.id
            const href = atlasTechniqueHref(tech)
            const desc = (tech.description || '').trim()
            const oneLine = desc.split(/\n/)[0]
            return (
              <article key={tid} className="atlas-technique-card" role="listitem">
                <div className="atlas-technique-top">
                  <span className="atlas-technique-id mono">{tid}</span>
                  {tech.tactic && (
                    <span className="atlas-tactic-badge mono">{tech.tactic}</span>
                  )}
                </div>
                <p className="atlas-technique-name">{tech.name}</p>
                {oneLine && <p className="atlas-technique-desc">{oneLine}</p>}
                {href && (
                  <a
                    className="atlas-technique-link mono"
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    atlas.mitre.org &rarr;
                  </a>
                )}
              </article>
            )
          })}
        </div>
      )}

      {studies.length > 0 && (
        <div className="atlas-case-studies">
          <h4 className="drawer-atlas-subhead mono">{formatSectionHeading('// RELATED CASE STUDIES')}</h4>
          <ul className="atlas-case-list">
            {studies.map(study => (
              <li key={study.study_id} className="atlas-case-item">
                <p className="atlas-case-name">{study.name}</p>
                {study.summary && (
                  <p className="atlas-case-summary">{study.summary}</p>
                )}
                <p className="atlas-case-meta mono">
                  {study.target || 'AI system'}
                  {study.incident_date ? ` · ${study.incident_date}` : ''}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
