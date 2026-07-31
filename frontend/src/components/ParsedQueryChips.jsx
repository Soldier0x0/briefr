import { removeChipFromQuery } from '../utils/feedQueryParser.js'
import './ParsedQueryChips.css'

export default function ParsedQueryChips({ chips, query, onQueryChange }) {
  if (!chips?.length) return null

  return (
    <div className="parsed-query-chips" role="list" aria-label="Understood search filters">
      <span className="parsed-query-label mono">Understood:</span>
      {chips.map((chip) => (
        <button
          key={`${chip.type}-${chip.label}`}
          type="button"
          className="parsed-query-chip mono"
          role="listitem"
          aria-label={`Remove ${chip.label} filter`}
          onClick={() => onQueryChange(removeChipFromQuery(query, chip))}
        >
          {chip.label}
          <span aria-hidden="true">×</span>
        </button>
      ))}
    </div>
  )
}
