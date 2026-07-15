import { collectNeedsAttentionItems } from '../needsAttention.js'

/**
 * Overview landing panel aggregating failures and degraded signals (E8-3).
 */
export default function NeedsAttentionPanel({ system, setPage, ingestErrorCount = 0, unackJobErrorCount = 0, mode = 'operator' }) {
  const items = collectNeedsAttentionItems(system, { ingestErrorCount, unackJobErrorCount, mode })
  if (items.length === 0) return null

  const errorCount = items.filter(i => i.severity === 'error').length
  const headline =
    errorCount > 0
      ? `${errorCount} critical item${errorCount === 1 ? '' : 's'} need attention`
      : `${items.length} item${items.length === 1 ? '' : 's'} need attention`

  return (
    <section className="admin-needs-attention" aria-labelledby="admin-needs-attention-title">
      <div className="admin-needs-attention-header">
        <h2 id="admin-needs-attention-title" className="admin-needs-attention-title">
          Needs attention
        </h2>
        <p className="admin-needs-attention-summary">{headline}</p>
      </div>
      <ul className="admin-needs-attention-list">
        {items.map(item => (
          <li
            key={item.id}
            className={`admin-needs-attention-item admin-needs-attention-item--${item.severity}`}
          >
            <div className="admin-needs-attention-copy">
              <div className="admin-needs-attention-item-title">{item.title}</div>
              {item.detail && (
                <p className="admin-needs-attention-item-detail">{item.detail}</p>
              )}
            </div>
            {setPage && item.pageId && (
              <button
                type="button"
                className="admin-btn admin-btn-ghost admin-needs-attention-action"
                onClick={() => setPage(item.pageId)}
              >
                {item.actionLabel || 'Open'}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
