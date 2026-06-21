import { AlertTriangle } from 'lucide-react'

export default function DangerZone({ title = 'Danger zone', children }) {
  return (
    <div className="admin-card danger-zone">
      <div className="danger-zone-title">
        <AlertTriangle size={13} strokeWidth={2.25} /> {title} — these actions cannot be undone
      </div>
      {children}
    </div>
  )
}
