import { safeExternalUrl } from '../../utils/safeExternalUrl.js'
import { severityColor, truncateText } from './helpers.js'

function RelatedNewsSection({ relatedNews }) {
  if (!relatedNews?.length) return null
  return (
    <section className="drawer-section" aria-labelledby="related-news-heading">
      <h3 id="related-news-heading" className="drawer-human-label drawer-tab-anchor mono">
        IN INCIDENTS &amp; NEWS
      </h3>
      <p className="drawer-related-lane-note mono">
        // Mentions of this CVE ID in the Incidents feed (RSS / ATLAS snapshot)
      </p>
      <ul className="drawer-related-news-list" aria-label="Related news articles">
        {relatedNews.map(item => {
          const href = safeExternalUrl(item.url)
          const key = `${item.url || item.title}-${item.publishedAt || ''}`
          return (
            <li key={key} className="drawer-related-news-item">
              <span className="drawer-related-news-source mono">{item.source || 'News'}</span>
              {href ? (
                <a href={href} target="_blank" rel="noopener noreferrer" className="drawer-related-news-title">
                  {item.title}
                </a>
              ) : (
                <span className="drawer-related-news-title">{item.title}</span>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export default function TabRelated({
  related,
  relatedMethod,
  relatedNews = [],
  loading,
  onSelectRelated,
}) {
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

  const hasRelated = related.length > 0
  const hasNews = relatedNews.length > 0

  if (!hasRelated && !hasNews) {
    return (
      <section className="drawer-section drawer-related-empty-wrap">
        <p className="drawer-related-empty mono">
          // No related CVEs or news mentions found for this CVE
        </p>
      </section>
    )
  }

  return (
    <>
      {hasRelated && (
        <section className="drawer-section" aria-labelledby="related-heading">
          <h3 id="related-heading" className="drawer-human-label drawer-tab-anchor mono">
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
                          {Math.round(Number(item.similarity) * 100)}% description similarity
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
      )}
      <RelatedNewsSection relatedNews={relatedNews} />
    </>
  )
}
