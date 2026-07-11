import NotificationBell from '../../../components/NotificationBell.jsx'

/** Admin status bar — operator-scope alerts only. */
export default function NotificationCenter() {
  return <NotificationBell scope="operator" />
}
