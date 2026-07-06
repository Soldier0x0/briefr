import { severityColor, truncateText } from './helpers.js'


export default function TabRelated({ related, relatedMethod, loading, onSelectRelated }) {
  const semantic = relatedMethod === 'embeddings'
  if (loading) {
    return (
      <section className="drawer-section drawer-related-loading" aria-busy="true">
        <ul className="drawer-related-skeleton-list" aria-label="Loading related CVEs">
          {[0, 1, 2].map(i => (
            <li key={i} className="drawer-related-skeleton" aria-hidden="true" />
          ))}
        </ul>
      </section>
    )
  }

  if (!related.length) {
    return (
      <section className="drawer-section drawer-related-empty-wrap">
        <p className="drawer-related-empty mono">
          // No related CVEs found in the last 30 days for this product
        </p>
      </section>
    )
  }

  return (
    <section className="drawer-section" aria-labelledby="related-heading">
      <h3 id="related-heading" className="drawer-human-label mono">
        {semantic ? 'SIMILAR DESCRIPTION' : 'SAME PRODUCT FAMILY'}
      </h3>
      <p className="drawer-related-lane-note mono">
        {semantic
          ? '// Semantic neighbor — not the same as campaign correlation'
          : '// Same affected product — not the same as campaign correlation'}
      </p>
      <ul className="drawer-related-list" aria-label="Related CVEs">
        {related.map(item => {
          const sev = (item.severity || '').toUpperCase()
          const sevCol = severityColor(item.severity)
          return (
            <li key={item.cve_id}>
              <button
                type="button"
                className="drawer-related-item"
                onClick={() => onSelectRelated(item.cve_id)}
                aria-label={`Open ${item.cve_id}`}
              >
                <div className="drawer-related-top">
                  <span className="drawer-related-id mono">{item.cve_id}</span>
                  {sev && (
                    <span
                      className="drawer-related-sev mono"
                      style={{ color: sevCol, borderColor: sevCol }}
                    >
                      {sev}
                    </span>
                  )}
                  {item.cvss_score != null && (
                    <span className="drawer-related-cvss mono">
                      CVSS {Number(item.cvss_score).toFixed(1)}
                    </span>
                  )}
                  {semantic && item.similarity != null && (
                    <span className="drawer-related-sim mono">
                      {Math.round(Number(item.similarity) * 100)}% MATCH
                    </span>
                  )}
                </div>
                <p className="drawer-related-desc">
                  {truncateText(item.description, 90)}
                </p>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
