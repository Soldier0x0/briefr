import { Clock } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from './ui/index.js'
import { useApiQueueLive } from '../hooks/useApiQueueLive.js'
import './ApiQueueIndicator.css'

export default function ApiQueueIndicator({ apiQueue, className = '', defaultOpen = false }) {
  const { summary } = useApiQueueLive(apiQueue)
  const { queued, active, count, tone, ariaLabel, groups, summaryStats } = summary
  const pending = Boolean(apiQueue?.has_pending || queued > 0 || active > 0)

  if (!pending) return null

  return (
    <div className={`api-queue-indicator ${className}`.trim()}>
      <DropdownMenu defaultOpen={defaultOpen}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className={`api-queue-btn api-queue-btn--${tone}`}
            aria-label={ariaLabel}
            title="Background enrichment queue — external API calls wait for provider limits"
          >
            <Clock size={14} strokeWidth={2} aria-hidden="true" />
            <span className="api-queue-count mono">{count}</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="api-queue-dropdown"
          align="end"
          sideOffset={6}
          collisionPadding={8}
          role="region"
          aria-label="API queue details"
        >
          <div className="api-queue-dropdown-title">Background sync</div>
          <p className="api-queue-dropdown-sub">
            External API calls are queued so nothing is dropped when providers throttle.
          </p>
          {summaryStats.length > 0 && (
            <div className="api-queue-summary mono" aria-live="polite">
              {summaryStats.map(stat => (
                <span key={stat.label} className="api-queue-summary-stat">
                  {stat.count} {stat.label}
                </span>
              ))}
            </div>
          )}
          {groups.length > 0 && (
            <div className="api-queue-requests">
              {groups.map(group => (
                <section key={group.sourceKey} className="api-queue-provider-group">
                  <div className="api-queue-provider-head">
                    <span className="api-queue-provider-label">{group.sourceLabel}</span>
                    <span className="api-queue-provider-count mono">{group.rows.length}</span>
                  </div>
                  <ul className="api-queue-provider-list">
                    {group.rows.map(row => (
                      <li
                        key={row.key}
                        className={`api-queue-request api-queue-request--${row.state}`}
                      >
                        <div className="api-queue-request-head">
                          <span className="api-queue-request-dot" aria-hidden="true">●</span>
                          <span className={`api-queue-request-state api-queue-request-state--${row.state}`}>
                            {row.stateLabel}
                          </span>
                        </div>
                        {row.displayLabel && (
                          <div className="api-queue-request-label">{row.displayLabel}</div>
                        )}
                        {row.contextId && (
                          <div className="api-queue-request-context mono">{row.contextId}</div>
                        )}
                        {row.detail && (
                          <div className="api-queue-request-detail">{row.detail}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
