import { useEffect, useState } from 'react'
import { fetchThreatModelScenarios } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import { SkeletonRows, StatusChip } from './shared.jsx'

export default function ScenariosView({
  profileStack,
  selectedTechnique,
  onSelectTechnique,
  onGeneratePack,
  generatingCve,
}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)

  useEffect(() => {
    if (!profileStack) {
      setData(null)
      return undefined
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    fetchThreatModelScenarios(profileStack)
      .then(payload => { if (!cancelled) setData(payload) })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to load threat scenarios')
          setErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [profileStack])

  return (
    <section className="fg-map" aria-label="Threat scenarios">
      <h2 className="fg-section-label mono">THREAT SCENARIOS</h2>
      {!profileStack ? (
        <p className="fg-panel-empty mono">
          // Load an asset profile to see environment threat scenarios for your stack
        </p>
      ) : loading ? (
        <SkeletonRows count={6} />
      ) : error ? (
        <div className="fg-error-block">
          <p className="fg-error mono">// {error}</p>
        </div>
      ) : !data?.scenarios?.length ? (
        <p className="fg-panel-empty mono">
          // No ATT&amp;CK techniques linked to CVEs matching your stack yet
        </p>
      ) : (
        <ul className="fg-scenario-list">
          {data.scenarios.map(scenario => (
            <li key={scenario.technique_id}>
              <article
                className={`fg-scenario-card${selectedTechnique === scenario.technique_id ? ' fg-scenario-card-active' : ''}`}
              >
                <button
                  type="button"
                  className="fg-scenario-head"
                  onClick={() => onSelectTechnique(scenario.technique_id)}
                >
                  <span className="fg-scenario-id mono">{scenario.technique_id}</span>
                  <span className="fg-scenario-name">{scenario.name}</span>
                  <StatusChip status={scenario.coverage_status} />
                </button>
                <p className="fg-scenario-body">{scenario.scenario}</p>
                {scenario.evidence_cves?.length > 0 && (
                  <div className="fg-scenario-evidence">
                    <span className="fg-section-label mono">CVE EVIDENCE</span>
                    <ul className="fg-scenario-cves">
                      {scenario.evidence_cves.map(cve => (
                        <li key={cve.cve_id} className="mono">
                          {cve.cve_id}
                          {cve.is_kev && <span className="fg-kev-badge" title="CISA Known Exploited Vulnerabilities — confirmed active exploitation in the wild">KEV</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {scenario.mitigations?.length > 0 && (
                  <div className="fg-scenario-actions">
                    {scenario.mitigations.map((action, idx) => (
                      <button
                        key={`${action.type}-${action.cve_id || idx}`}
                        type="button"
                        className="admin-btn admin-btn-ghost fg-scenario-action mono"
                        disabled={action.type === 'hunt_pack' && generatingCve === action.cve_id}
                        onClick={() => {
                          if (action.type === 'hunt_pack' && action.cve_id) {
                            onGeneratePack(action.cve_id, action.technique_id)
                          } else {
                            onSelectTechnique(action.technique_id || scenario.technique_id)
                          }
                        }}
                      >
                        {action.type === 'hunt_pack' && generatingCve === action.cve_id
                          ? 'GENERATING…'
                          : action.label}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
