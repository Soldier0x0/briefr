import { CheckCircle2, AlertTriangle, XCircle, CircleDashed } from 'lucide-react'
import { fmtIso } from './formatters.js'
import ToggleSwitch from './shared/ToggleSwitch.jsx'

function sourceBadge(source) {
  if (source === 'env') {
    return <span className="badge badge-info" title="Bootstrapped from .env">env</span>
  }
  return <span className="badge badge-muted" title="Created in BRIEFR">db</span>
}

function configSummary(dest) {
  const cfg = dest.config || {}
  if (dest.kind === 'telegram') {
    const parts = []
    if (cfg.token) parts.push(`token: ${cfg.token}`)
    if (cfg.chat_id) parts.push(`chat: ${cfg.chat_id}`)
    return parts.join(' · ') || '—'
  }
  if (cfg.url) return cfg.url
  return '—'
}

function healthPresentation(health, enabled) {
  if (!enabled) {
    return {
      border: 'var(--border)',
      badge: 'badge-muted',
      label: 'Disabled',
      Icon: CircleDashed,
    }
  }
  if (!health?.last_attempt_at) {
    return {
      border: 'var(--border)',
      badge: 'badge-muted',
      label: 'No deliveries yet',
      Icon: CircleDashed,
    }
  }
  if (health.last_status === 'ok') {
    return {
      border: 'var(--green)',
      badge: 'badge-ok',
      label: 'Last delivery OK',
      Icon: CheckCircle2,
    }
  }
  if (health.failed_24h > 0 && health.ok_24h === 0) {
    return {
      border: 'var(--red)',
      badge: 'badge-error',
      label: 'Recent failures',
      Icon: XCircle,
    }
  }
  return {
    border: 'var(--amber)',
    badge: 'badge-warn',
    label: 'Last delivery failed',
    Icon: AlertTriangle,
  }
}

function HealthLine({ label, value, error = false }) {
  return (
    <div className="webhook-dest-health-line">
      <span className="webhook-dest-health-key">{label}</span>
      <span className={`webhook-dest-health-val mono${error ? ' webhook-dest-health-val--error' : ''}`}>
        {value || '—'}
      </span>
    </div>
  )
}

export default function WebhookDestinationCard({
  dest,
  health,
  testResult,
  testing,
  saving,
  onToggleEnabled,
  onTest,
  onEditEvents,
  onEditConfig,
  onDelete,
}) {
  const hp = healthPresentation(health, dest.enabled)
  const StatusIcon = hp.Icon
  const eventsCount = dest.event_types?.length || 0

  return (
    <article
      className={`feed-source-card webhook-dest-card${dest.enabled ? '' : ' webhook-dest-card--disabled'}`}
      style={{ borderLeftColor: hp.border }}
    >
      <div className="webhook-dest-card-head">
        <div style={{ minWidth: 0 }}>
          <div className="webhook-dest-card-title">{dest.label || dest.id}</div>
          <div className="webhook-dest-card-id">{dest.id}</div>
        </div>
        <ToggleSwitch
          on={!!dest.enabled}
          disabled={!!saving}
          onChange={onToggleEnabled}
          aria-label={`Enable ${dest.id}`}
        />
      </div>

      <div className="webhook-dest-card-meta">
        <span className="badge badge-muted" style={{ textTransform: 'capitalize' }}>{dest.kind}</span>
        {sourceBadge(dest.source)}
        <span className={`badge ${hp.badge}`}>
          <StatusIcon size={11} strokeWidth={2.25} style={{ marginRight: '0.25rem', verticalAlign: '-1px' }} />
          {hp.label}
        </span>
        {testResult && (
          <span className={`badge ${testResult.ok ? 'badge-ok' : 'badge-error'}`}>
            test {testResult.ok ? 'ok' : 'fail'}
          </span>
        )}
      </div>

      <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--text3)' }} title={configSummary(dest)}>
        {configSummary(dest)}
      </div>

      <div className="webhook-dest-health-lines">
        <HealthLine label="success" value={fmtIso(health?.last_success_at)} />
        <HealthLine label="failure" value={fmtIso(health?.last_failure_at)} />
        <HealthLine
          label="24h"
          value={
            health
              ? `${health.ok_24h ?? 0} ok · ${health.failed_24h ?? 0} fail`
              : '0 ok · 0 fail'
          }
        />
        {health?.last_error && (
          <HealthLine label="error" value={health.last_error} error />
        )}
      </div>

      <div style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>
        {eventsCount} event{eventsCount === 1 ? '' : 's'} subscribed
      </div>

      <div className="webhook-dest-actions">
        <button
          type="button"
          className="admin-btn admin-btn-ghost"
          style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}
          onClick={onTest}
          disabled={testing}
        >
          {testing ? 'Testing…' : 'Test send'}
        </button>
        <button
          type="button"
          className="admin-btn admin-btn-ghost"
          style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}
          onClick={onEditEvents}
        >
          Events
        </button>
        {dest.source === 'db' && (
          <button
            type="button"
            className="admin-btn admin-btn-ghost"
            style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}
            onClick={onEditConfig}
          >
            Config
          </button>
        )}
        <button
          type="button"
          className="admin-btn admin-btn-ghost"
          style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', color: 'var(--danger)' }}
          onClick={onDelete}
        >
          Delete
        </button>
      </div>
    </article>
  )
}
