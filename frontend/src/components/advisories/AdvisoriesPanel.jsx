import { useCallback, useEffect, useState } from 'react'
import { fetchPublications } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import { PublicationCard, SkeletonCards } from './shared.jsx'

export default function AdvisoriesPanel({ onOpenCve }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setFailed(false)
    fetchPublications({ limit: 50 })
      .then(body => {
        if (cancelled) return
        setRows(Array.isArray(body?.data) ? body.data : [])
      })
      .catch(err => {
        if (!cancelled) {
          setRows([])
          setFailed(true)
          notifyApiError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => load(), [load])

  return (
    <section className="cs-panel" aria-labelledby="cs-advisories-heading">
      <h2 id="cs-advisories-heading" className="cs-section-label mono">ADVISORIES</h2>
      {loading ? (
        <SkeletonCards count={4} />
      ) : failed ? (
        <p className="cs-empty mono">// Failed to load publications</p>
      ) : rows.length === 0 ? (
        <p className="cs-empty mono">
          // No structured publications yet — scheduler sync runs when{' '}
          <code>PUBLICATION_SYNC_ENABLED=1</code> on the server
        </p>
      ) : (
        <div className="cs-feed">
          {rows.map(row => (
            <PublicationCard key={row.publication_id} row={row} onOpenCve={onOpenCve} />
          ))}
        </div>
      )}
      {failed && (
        <button type="button" className="cs-retry-btn mono" onClick={load}>
          Retry
        </button>
      )}
    </section>
  )
}
