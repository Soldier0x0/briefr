export default function DangerZone({ title = 'Danger zone', children }) {
  return (
    <div className="admin-card danger-zone">
      <div className="danger-zone-title">⚠ {title} — these actions cannot be undone</div>
      {children}
    </div>
  )
}
