import { ADMIN_MODE_LABELS, resolveAdminPage } from '../constants.js'

function upperLabel(text) {
  return String(text || '').toUpperCase()
}

/**
 * "You are here" trail for the admin shell (E8-2).
 * Admin → view mode → section → current page.
 */
export default function AdminBreadcrumbs({ pageId, mode, setPage }) {
  const { section, label } = resolveAdminPage(pageId, mode)
  const modeLabel = upperLabel(ADMIN_MODE_LABELS[mode] || mode)

  return (
    <nav className="admin-breadcrumbs" aria-label="You are here">
      <button
        type="button"
        className="admin-breadcrumb-link"
        onClick={() => setPage('overview')}
      >
        ADMIN
      </button>
      <span className="admin-breadcrumb-sep" aria-hidden="true">›</span>
      <span className="admin-breadcrumb-segment">{modeLabel}</span>
      {section && (
        <>
          <span className="admin-breadcrumb-sep" aria-hidden="true">›</span>
          <span className="admin-breadcrumb-segment admin-breadcrumb-section">{upperLabel(section)}</span>
        </>
      )}
      <span className="admin-breadcrumb-sep" aria-hidden="true">›</span>
      <span className="admin-breadcrumb-current" aria-current="page">{upperLabel(label)}</span>
    </nav>
  )
}
