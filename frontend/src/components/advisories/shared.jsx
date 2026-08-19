import {
  highlightParts,
  relativeDate,
} from '../../utils/caseStudyFeed.js'
import { safeExternalUrl } from '../../utils/safeExternalUrl.js'

export function SkeletonCards({ count = 4 }) {
  return (
    <ul className="cs-skeleton-list" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="cs-skeleton-card" />
      ))}
    </ul>
  )
}

export function TechniqueChips({ techniques }) {
  if (!techniques?.length) return null
  return (
    <div className="cs-tech-chips" aria-label="Techniques referenced">
      {techniques.slice(0, 6).map(tid => (
        <span key={tid} className="cs-tech-chip mono">{tid}</span>
      ))}
    </div>
  )
}

export function CveChips({ cveIds, onOpenCve }) {
  if (!cveIds?.length) return null
  const uniqueCves = Array.from(
    new Set(cveIds.map(id => String(id || '').toUpperCase()).filter(Boolean)),
  )
  if (!uniqueCves.length) return null
  const shown = uniqueCves.slice(0, 6)
  const extra = uniqueCves.length - shown.length
  return (
    <div className="cs-cve-chips" aria-label="CVE IDs mentioned">
      {shown.map(id => (
        onOpenCve ? (
          <button
            key={id}
            type="button"
            className="cs-cve-chip mono"
            onClick={() => onOpenCve(id)}
            title={`Open ${id} in drawer`}
          >
            {id}
          </button>
        ) : (
          <span key={id} className="cs-cve-chip mono">{id}</span>
        )
      ))}
      {extra > 0 && (
        <span className="cs-cve-chip cs-cve-chip-more mono" title={uniqueCves.slice(6).join(', ')}>
          +{extra}
        </span>
      )}
    </div>
  )
}

export function FeedCard({ card, query, onOpenCve }) {
  const titleParts = highlightParts(card.title, query)
  const descParts = highlightParts(card.description, query)
  const safeUrl = safeExternalUrl(card.url)

  return (
    <article className="cs-card">
      <div className="cs-card-top">
        <span className={`cs-source-badge mono${card.kind === 'atlas' ? ' cs-source-badge-atlas' : ''}`}>
          {card.source}
        </span>
        <time className="cs-card-date mono" dateTime={card.publishedAt}>
          {relativeDate(card.publishedAt)}
        </time>
      </div>
      <h3 className="cs-card-title">
        {safeUrl ? (
          <a href={safeUrl} target="_blank" rel="noopener noreferrer">
            {titleParts.map((p, i) =>
              p.match ? <mark key={i} className="cs-highlight">{p.text}</mark> : <span key={i}>{p.text}</span>,
            )}
          </a>
        ) : (
          <span>
            {titleParts.map((p, i) =>
              p.match ? <mark key={i} className="cs-highlight">{p.text}</mark> : <span key={i}>{p.text}</span>,
            )}
          </span>
        )}
      </h3>
      {card.actor && (
        <p className="cs-card-actor mono">Actor: {card.actor}</p>
      )}
      {card.target && card.kind === 'atlas' && (
        <p className="cs-card-target mono">Target: {card.target}</p>
      )}
      <p className="cs-card-desc">
        {descParts.map((p, i) =>
          p.match ? <mark key={i} className="cs-highlight">{p.text}</mark> : <span key={i}>{p.text}</span>,
        )}
      </p>
      <CveChips cveIds={card.cve_ids} onOpenCve={onOpenCve} />
      <TechniqueChips techniques={card.techniques} />
    </article>
  )
}

export function PublicationCard({ row, onOpenCve }) {
  const safeUrl = safeExternalUrl(row.canonical_url)
  const published = row.published_at || row.retrieved_at

  return (
    <article className="cs-card cs-card-publication">
      <div className="cs-card-top">
        <span className="cs-source-badge mono">{row.source_key}</span>
        <time className="cs-card-date mono" dateTime={published}>
          {relativeDate(published)}
        </time>
      </div>
      <h3 className="cs-card-title">
        {safeUrl ? (
          <a href={safeUrl} target="_blank" rel="noopener noreferrer">
            {row.title}
          </a>
        ) : (
          <span>{row.title}</span>
        )}
      </h3>
      <p className="cs-card-meta mono">
        {row.document_kind}
        {row.extraction_status === 'complete' ? '' : ` · ${row.extraction_status}`}
      </p>
      <CveChips cveIds={row.cve_ids} onOpenCve={onOpenCve} />
    </article>
  )
}
