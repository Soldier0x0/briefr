/** Thin status strip shown while an admin action is in flight. */
export default function ActionProgress({ label, stage, visible }) {
  if (!visible || !label) return null
  return (
    <div className="admin-action-progress" role="status" aria-live="polite">
      <span className="admin-spinner" aria-hidden="true" />
      <span className="admin-action-progress-label">{label}</span>
      {stage && <span className="admin-action-progress-stage">{stage}</span>}
    </div>
  )
}
