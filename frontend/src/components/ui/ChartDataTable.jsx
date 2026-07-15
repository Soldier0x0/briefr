import './ui.css'

/**
 * Collapsible tabular fallback for chart data (E6-5 a11y).
 * Screen readers and keyboard users can access the same values without the canvas.
 */
export default function ChartDataTable({ title, columns, rows, className = '' }) {
  if (!rows?.length || !columns?.length) return null

  return (
    <details className={`chart-data-table${className ? ` ${className}` : ''}`}>
      <summary className="chart-data-table-summary mono">View chart data as table</summary>
      <div className="chart-data-table-wrap">
        <table aria-label={title}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={col.headerClassName || col.className || ''}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row._key ?? index}>
                {columns.map((col) => (
                  <td key={col.key} className={col.className || ''}>
                    {col.render ? col.render(row, index) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
