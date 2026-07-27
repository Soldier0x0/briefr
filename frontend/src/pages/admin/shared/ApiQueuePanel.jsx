import ApiQueueIndicator from '../../../components/ApiQueueIndicator.jsx'
import { useApiQueueLive } from '../../../hooks/useApiQueueLive.js'

export default function ApiQueuePanel({ apiQueue }) {
  const { summary } = useApiQueueLive(apiQueue)
  const pending = Boolean(apiQueue?.has_pending || summary.count > 0)
  if (!pending) return null

  return (
    <div className="admin-card">
      <div className="admin-card-header-row">
        <div>
          <div className="admin-card-title">Outbound API queue</div>
          <p className="admin-page-subtitle">
            External calls wait for provider rate limits — nothing is dropped. Retry timers
            update every second.
          </p>
        </div>
        <ApiQueueIndicator apiQueue={apiQueue} className="api-queue-indicator--admin" />
      </div>
      {summary.groups.length > 0 && (
        <ul className="api-queue-panel-list">
          {summary.groups.map(group => (
            <li key={group.sourceKey}>
              <strong>{group.sourceLabel}</strong>
              {group.rows.map(row => (
                <div key={row.key} className="api-queue-panel-row mono">
                  <span>{row.stateLabel}</span>
                  {row.displayLabel && <span>{row.displayLabel}</span>}
                  {row.detail && <span>{row.detail}</span>}
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
