function parseVendors(vendorsStr) {
  if (!vendorsStr?.trim()) return []
  return vendorsStr.split(',').map(v => v.trim()).filter(Boolean)
}

export default function ActiveFilterChips({ filters, onFiltersChange }) {
  const chips = []

  if (filters.kev_only) chips.push({ key: 'kev', label: 'KEV', clear: { kev_only: false } })
  if (filters.kev_overdue_only) chips.push({ key: 'kev_overdue', label: 'KEV overdue', clear: { kev_overdue_only: false } })
  if (filters.poc_only) chips.push({ key: 'poc', label: 'PoC', clear: { poc_only: false } })
  if (filters.watchlist_only) chips.push({ key: 'watchlist', label: 'Watchlist', clear: { watchlist_only: false } })
  if (filters.severity) chips.push({ key: 'sev', label: filters.severity, clear: { severity: null } })
  if (filters.epss_min != null) chips.push({ key: 'epss', label: 'EPSS > 50%', clear: { epss_min: null } })
  if (filters.my_stack_only) chips.push({ key: 'stack_only', label: 'My stack only', clear: { my_stack_only: false } })
  if (filters.search?.trim()) chips.push({ key: 'search', label: `"${filters.search.trim()}"`, clear: { search: '' } })
  if (filters.technique) chips.push({ key: 'technique', label: filters.technique, clear: { technique: '' } })
  if (filters.published_on) chips.push({ key: 'pub', label: filters.published_on, clear: { published_on: '' } })
  if (filters.ai_profile_match) chips.push({ key: 'ai', label: 'AI profile match', clear: { ai_profile_match: false } })

  parseVendors(filters.vendors).forEach(v => {
    chips.push({
      key: `vendor-${v}`,
      label: v,
      clear: {
        vendors: parseVendors(filters.vendors).filter(x => x !== v).join(','),
      },
    })
  })

  if (!chips.length) return null

  function clearAll() {
    onFiltersChange({
      severity: null,
      kev_only: false,
      kev_overdue_only: false,
      poc_only: false,
      epss_min: null,
      search: '',
      vendors: '',
      technique: '',
      published_on: '',
      my_stack_only: false,
      watchlist_only: false,
      ai_profile_match: false,
    })
  }

  return (
    <div className="active-filters" role="region" aria-label="Active filters">
      <span className="active-filters-label">Filters</span>
      {chips.map(c => (
        <button
          key={c.key}
          type="button"
          className="chip chip-active chip-removable"
          onClick={() => onFiltersChange(c.clear)}
          aria-label={`Remove filter ${c.label}`}
        >
          {c.label}
          <span aria-hidden="true">×</span>
        </button>
      ))}
      {chips.length > 1 && (
        <button type="button" className="btn btn-ghost" onClick={clearAll}>
          Clear all
        </button>
      )}
    </div>
  )
}
