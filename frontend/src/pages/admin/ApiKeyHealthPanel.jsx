import { useMemo } from 'react'
import { RefreshCw } from 'lucide-react'
import { fmtIso } from './formatters.js'
import HelpTip from './shared/HelpTip.jsx'
import AdminDataGrid from './shared/AdminDataGrid.jsx'
import AsyncSection from './shared/AsyncSection.jsx'

const PROVIDER_LABELS = {
  nvd: 'NVD',
  groq: 'Groq',
  gemini: 'Google Gemini',
  cerebras: 'Cerebras',
  openrouter: 'OpenRouter',
  virustotal: 'VirusTotal',
  github: 'GitHub',
  otx: 'AlienVault OTX',
  greynoise: 'GreyNoise',
  abuseipdb: 'AbuseIPDB',
}

export function providerLabel(id) {
  return PROVIDER_LABELS[id] || id
}

function healthStatus(row) {
  if (!row.configured) {
    return { label: 'Not configured', badge: 'badge-muted' }
  }
  if (row.healthy === true) {
    return { label: 'Healthy', badge: 'badge-ok' }
  }
  if (row.healthy === false) {
    return { label: 'Unhealthy', badge: 'badge-error' }
  }
  return { label: 'Not checked', badge: 'badge-warn' }
}

export default function ApiKeyHealthPanel({
  health,
  loading,
  error,
  running,
  onRefresh,
  onRun,
}) {
  const columns = useMemo(() => [
    {
      id: 'provider',
      label: 'Provider',
      defaultVisible: true,
      render: (row) => providerLabel(row.provider),
    },
    {
      id: 'env_key',
      label: 'Env key',
      defaultVisible: true,
      render: (row) => <span className="mono">{row.env_key}</span>,
    },
    {
      id: 'suffix',
      label: 'Suffix',
      defaultVisible: true,
      render: (row) => (
        <span className="mono" title="First and last four characters of the configured key">
          {row.key_suffix || '—'}
        </span>
      ),
    },
    {
      id: 'status',
      label: 'Health',
      defaultVisible: true,
      render: (row) => {
        const { label, badge } = healthStatus(row)
        return <span className={`badge ${badge}`}>{label}</span>
      },
    },
    {
      id: 'last_checked',
      label: 'Last checked',
      defaultVisible: true,
      render: (row) => <span className="mono">{fmtIso(row.last_checked_at)}</span>,
    },
    {
      id: 'latency',
      label: 'Latency',
      defaultVisible: true,
      render: (row) => (
        <span className="mono">
          {row.latency_ms != null ? `${row.latency_ms} ms` : '—'}
        </span>
      ),
    },
    {
      id: 'error',
      label: 'Last error',
      defaultVisible: true,
      render: (row) => (
        <span style={{ color: row.error ? 'var(--amber)' : 'var(--text3)', wordBreak: 'break-word' }}>
          {row.error ? String(row.error).slice(0, 120) : '—'}
        </span>
      ),
    },
  ], [])

  const rows = health?.providers || []
  const summary = health
    ? `${health.healthy_count ?? 0} healthy / ${health.configured_count ?? 0} configured`
    : ''

  return (
    <div className="admin-card" style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="admin-card-title" style={{ margin: 0 }}>
          Provider health
          <HelpTip text="Configured means a non-placeholder value is set in the environment. Healthy means the last scheduler or manual ping succeeded. These checks are separate from outbound API quota pacing and inbound rate limits on your BRIEFR instance." />
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {summary && (
            <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
              {summary}
              {health.checked_at ? ` · last sweep ${fmtIso(health.checked_at)}` : ''}
            </span>
          )}
          <button
            type="button"
            className="admin-btn admin-btn-ghost"
            style={{ fontSize: '0.75rem' }}
            disabled={loading || running}
            onClick={onRefresh}
          >
            Refresh
          </button>
          <button
            type="button"
            className="admin-btn admin-btn-primary"
            style={{ fontSize: '0.75rem' }}
            disabled={loading || running}
            onClick={onRun}
          >
            {running
              ? <><span className="admin-spinner" /> Running checks…</>
              : <><RefreshCw size={12} style={{ marginRight: '0.35rem', verticalAlign: '-2px' }} />Run check now</>}
          </button>
        </div>
      </div>
      <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0.5rem 0 0.75rem' }}>
        Scheduled job: <code className="mono">api_key_health_check</code> (Admin → Scheduler).
        Optional keys can stay unconfigured — they are skipped by the ping sweep.
      </p>
      <AsyncSection
        data={error ? null : rows}
        error={error}
        loading={loading}
        onRetry={onRefresh}
        emptyMessage="No provider rows returned"
      >
        {(providerRows) => (
          <AdminDataGrid
            gridId="api-key-health"
            columns={columns}
            rows={providerRows}
            rowKey={(row) => row.provider}
            emptyMessage="No providers"
          />
        )}
      </AsyncSection>
    </div>
  )
}
