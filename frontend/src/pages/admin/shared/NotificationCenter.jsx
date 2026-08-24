import NotificationBell from '../../../components/NotificationBell.jsx'
import { useAuth } from '../../../context/AuthContext.jsx'

/** Admin status bar — unified inbox (intel + ops) for admins; analyst scope elsewhere. */
export default function NotificationCenter() {
  const { user } = useAuth()
  const notificationScope = user?.role === 'admin' ? 'all' : 'analyst'
  return <NotificationBell scope={notificationScope} />
}
