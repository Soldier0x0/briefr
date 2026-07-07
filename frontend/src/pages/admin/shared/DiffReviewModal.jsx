// Generic pending-changes review modal: shows a {key: value} diff, lets the
// operator discard or apply. Used by any page with a queue/diff-review flow
// (config apply-all today; reusable for future bulk-edit flows).
export default function DiffReviewModal({ title = 'Review pending changes', changes, secretKeyPredicate, onApply, onDiscard, onClose, applying = false, applyLabel = 'Save changes' }) {
  const isSecret = secretKeyPredicate || (k => k.endsWith('_KEY') || k.endsWith('_TOKEN') || k.endsWith('_SECRET'))
  return (
    <div className="admin-modal-overlay">
      <div className="admin-modal" style={{ minWidth: 480 }}>
        <div className="admin-modal-title">{title}</div>
        <table className="admin-table" style={{ marginTop: '0.5rem' }}>
          <thead><tr><th>KEY</th><th>NEW VALUE</th></tr></thead>
          <tbody>
            {Object.entries(changes).map(([k, v]) => (
              <tr key={k}>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{k}</td>
                <td style={{ fontSize: '0.8125rem' }}>{isSecret(k) ? '••••' : v}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="admin-modal-actions">
          <button className="admin-btn admin-btn-ghost" onClick={onClose}>Close</button>
          <button className="admin-btn admin-btn-danger" onClick={onDiscard}>Discard all</button>
          <button className="admin-btn admin-btn-primary" onClick={onApply} disabled={applying}>
            {applyLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
