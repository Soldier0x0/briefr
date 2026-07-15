import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Checkbox } from '../../../components/ui/index.js'

const STORAGE_PREFIX = 'briefr-grid-'

function loadPrefs(gridId, columnIds) {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${gridId}`)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    const visible = Array.isArray(parsed.visible)
      ? parsed.visible.filter((id) => columnIds.includes(id))
      : null
    return {
      visible,
      wrap: Boolean(parsed.wrap),
      center: Boolean(parsed.center),
      widths: parsed.widths && typeof parsed.widths === 'object' ? parsed.widths : {},
    }
  } catch {
    return null
  }
}

function savePrefs(gridId, prefs) {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${gridId}`, JSON.stringify(prefs))
  } catch { /* unavailable */ }
}

/**
 * Dense admin table: column picker, optional wrap/center, header resize via shared <col> widths.
 */
export default function AdminDataGrid({
  gridId,
  columns,
  rows,
  rowKey = (row, index) => index,
  emptyMessage = 'No rows',
  toolbarExtra = null,
  onRowClick = null,
  activeRowKey = null,
}) {
  const columnIds = useMemo(() => columns.map((c) => c.id), [columns])
  const defaultVisible = useMemo(
    () => columns.filter((c) => c.defaultVisible !== false).map((c) => c.id),
    [columns],
  )

  const [visibleIds, setVisibleIds] = useState(() => {
    const prefs = loadPrefs(gridId, columnIds)
    return prefs?.visible?.length ? prefs.visible : defaultVisible
  })
  const [wrapCells, setWrapCells] = useState(() => {
    const prefs = loadPrefs(gridId, columnIds)
    return prefs ? prefs.wrap : false
  })
  const [centerCells, setCenterCells] = useState(() => {
    const prefs = loadPrefs(gridId, columnIds)
    return prefs ? prefs.center : false
  })
  const [widths, setWidths] = useState(() => {
    const prefs = loadPrefs(gridId, columnIds)
    return prefs ? prefs.widths : {}
  })
  const [showColumns, setShowColumns] = useState(false)
  const resizeRef = useRef({ colId: null, startX: 0, startW: 0 })

  useEffect(() => {
    const prefs = loadPrefs(gridId, columnIds)
    setVisibleIds(prefs?.visible?.length ? prefs.visible : defaultVisible)
    setWrapCells(prefs ? prefs.wrap : false)
    setCenterCells(prefs ? prefs.center : false)
    setWidths(prefs ? prefs.widths : {})
  }, [gridId, defaultVisible])

  useEffect(() => {
    savePrefs(gridId, { visible: visibleIds, wrap: wrapCells, center: centerCells, widths })
  }, [gridId, visibleIds, wrapCells, centerCells, widths])

  const visibleColumns = useMemo(
    () => columns.filter((c) => visibleIds.includes(c.id)),
    [columns, visibleIds],
  )

  const onResizeMove = useCallback((e) => {
    const { colId, startX, startW } = resizeRef.current
    if (!colId) return
    const next = Math.max(72, Math.min(640, startW + (e.clientX - startX)))
    setWidths((w) => ({ ...w, [colId]: next }))
  }, [])

  const onResizeEnd = useCallback(() => {
    resizeRef.current.colId = null
    window.removeEventListener('mousemove', onResizeMove)
    window.removeEventListener('mouseup', onResizeEnd)
  }, [onResizeMove])

  useEffect(() => () => {
    window.removeEventListener('mousemove', onResizeMove)
    window.removeEventListener('mouseup', onResizeEnd)
  }, [onResizeMove, onResizeEnd])

  function startResize(colId, e) {
    e.preventDefault()
    const th = e.currentTarget.closest('th')
    const startW = widths[colId] || th?.offsetWidth || 120
    resizeRef.current = { colId, startX: e.clientX, startW }
    window.addEventListener('mousemove', onResizeMove)
    window.addEventListener('mouseup', onResizeEnd)
  }

  function toggleColumn(id) {
    setVisibleIds((prev) => {
      if (prev.includes(id)) {
        if (prev.length <= 1) return prev
        return prev.filter((x) => x !== id)
      }
      const order = columnIds.filter((c) => prev.includes(c) || c === id)
      return order
    })
  }

  const colStyle = (col) => {
    const w = widths[col.id]
    const widthPx = w || col.width
    return {
      width: widthPx ? `${widthPx}px` : undefined,
      minWidth: widthPx
        ? `${widthPx}px`
        : col.minWidth
          ? `${col.minWidth}px`
          : '72px',
    }
  }

  const cellStyle = (col) => ({
    textAlign: centerCells || col.align === 'center' ? 'center' : 'left',
    whiteSpace: wrapCells ? 'normal' : 'nowrap',
    overflow: wrapCells ? 'visible' : 'hidden',
    textOverflow: wrapCells ? 'clip' : 'ellipsis',
    wordBreak: wrapCells ? 'break-word' : 'normal',
    verticalAlign: 'top',
  })

  return (
    <div className="admin-data-grid">
      <div className="admin-data-grid-toolbar">
        <div className="admin-data-grid-toolbar-left">
          <button type="button" className="admin-btn admin-btn-ghost admin-data-grid-btn"
            onClick={() => setShowColumns((v) => !v)}>
            Columns ({visibleColumns.length}/{columns.length})
          </button>
          {showColumns && (
            <div className="admin-data-grid-col-picker" role="group" aria-label="Visible columns">
              {columns.map((c) => (
                <Checkbox
                  key={c.id}
                  id={`${gridId}-col-${c.id}`}
                  checked={visibleIds.includes(c.id)}
                  onCheckedChange={() => toggleColumn(c.id)}
                  label={c.label}
                  className="admin-data-grid-col-option"
                />
              ))}
            </div>
          )}
          <Checkbox
            id={`${gridId}-wrap`}
            checked={wrapCells}
            onCheckedChange={setWrapCells}
            label="Wrap"
            className="admin-data-grid-toggle"
          />
          <Checkbox
            id={`${gridId}-center`}
            checked={centerCells}
            onCheckedChange={setCenterCells}
            label="Center"
            className="admin-data-grid-toggle"
          />
        </div>
        {toolbarExtra}
      </div>

      <div className="admin-data-grid-scroll">
        <table className="admin-table admin-data-grid-table">
          <colgroup>
            {visibleColumns.map((col) => (
              <col key={col.id} style={colStyle(col)} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {visibleColumns.map((col) => (
                <th
                  key={col.id}
                  className="admin-data-grid-th"
                  style={cellStyle(col)}
                  title={col.label}
                >
                  <span className="admin-data-grid-th-label">{col.label}</span>
                  <span
                    className="admin-data-grid-resize-handle"
                    role="separator"
                    aria-orientation="vertical"
                    onMouseDown={(e) => startResize(col.id, e)}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={visibleColumns.length} className="admin-empty">{emptyMessage}</td>
              </tr>
            )}
            {rows.map((row, index) => (
              <tr
                key={rowKey(row, index)}
                className={onRowClick ? 'admin-data-grid-row-clickable' : undefined}
                aria-selected={activeRowKey != null && rowKey(row, index) === activeRowKey ? true : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {visibleColumns.map((col) => (
                  <td key={col.id} style={cellStyle(col)} title={typeof col.title === 'function' ? col.title(row) : (col.title || undefined)}>
                    {col.render ? col.render(row) : String(row[col.id] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
