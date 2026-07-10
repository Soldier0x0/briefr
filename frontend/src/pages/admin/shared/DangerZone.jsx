import { AlertTriangle } from 'lucide-react'

export default function DangerZone({ title = 'Danger zone', children, subdued = false }) {
  return (
    <div className={`admin-danger-zone danger-zone${subdued ? ' admin-danger-zone--subdued' : ''}`}>
      <h2 className="admin-danger-zone-title danger-zone-title">
        <AlertTriangle size={14} strokeWidth={2.25} aria-hidden />
        {title}
      </h2>
      <p className="admin-danger-zone-desc">These actions are destructive and cannot be undone. Read each description carefully.</p>
      {children}
    </div>
  )
}
