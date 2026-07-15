import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import Checkbox from './Checkbox.jsx'
import {
  layoutPrefsKey,
  loadLayoutPrefs,
  saveLayoutPrefs,
} from '../../utils/gridLayoutPrefs.js'
import './DataGrid.css'

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
      widths: parsed.widths && typeof parsed.widths === 'object' ? parsed.widths : {},
      /** @deprecated migrated to gridLayoutPrefs */
      wrap: Boolean(parsed.wrap),
      /** @deprecated migrated to gridLayoutPrefs */
      center: Boolean(parsed.center),
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

function sortValueForColumn(col, row) {
  if (typeof col.sortValue === 'function') return col.sortValue(row)
  return row[col.id]
}

function compareSortValues(a, b) {
  if (a == null && b == null) return 0
  if (a == null) return 1
  if (b == null) return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' })
}

/**
 * Shared table primitive: fixed layout, sticky header, sortable columns,
 * resize via shared <col>, optional wrap/center, persisted column prefs.
 */
export default function DataGrid({
  gridId,
  columns,
  rows,
  rowKey = (row, index) => row.id ?? row.uuid ?? index,
  emptyMessage = 'No rows',
  toolbarExtra = null,
  onRowClick = null,
  activeRowKey = null,
  className = '',
  tableClassName = 'data-grid-table',
  stickyHeader = true,
  layoutGroupId = null,
  showLayoutToggles = true,
  layoutWrap,
  layoutCenter,
}) {
  const columnIds = useMemo(() => columns.map((c) => c.id), [columns])
  const defaultVisible = useMemo(
    () => columns.filter((c) => c.defaultVisible !== false).map((c) => c.id),
    [columns],
  )

  const [prefs] = useState(() => loadPrefs(gridId, columnIds))
  const layoutKey = layoutPrefsKey(gridId, layoutGroupId)
  const [layoutPrefs] = useState(() => {
    const fromLayout = loadLayoutPrefs(layoutKey)
    if (fromLayout.wrap || fromLayout.center) return fromLayout
    if (prefs?.wrap || prefs?.center) return { wrap: Boolean(prefs.wrap), center: Boolean(prefs.center) }
    return fromLayout
  })
  const [visibleIds, setVisibleIds] = useState(() => {
    return prefs?.visible?.length ? prefs.visible : defaultVisible
  })
  const [wrapCellsInternal, setWrapCellsInternal] = useState(() => layoutPrefs.wrap)
  const [centerCellsInternal, setCenterCellsInternal] = useState(() => layoutPrefs.center)
  const isLayoutControlled = layoutWrap !== undefined && layoutCenter !== undefined
  const wrapCells = isLayoutControlled ? layoutWrap : wrapCellsInternal
  const centerCells = isLayoutControlled ? layoutCenter : centerCellsInternal
  const [widths, setWidths] = useState(() => {
    return prefs ? prefs.widths : {}
  })
  const [sorting, setSorting] = useState([])
  const [showColumns, setShowColumns] = useState(false)
  const resizeRef = useRef({ colId: null, startX: 0, startW: 0 })
  const isLoadingRef = useRef(false)

  useEffect(() => {
    isLoadingRef.current = true
    const nextPrefs = loadPrefs(gridId, columnIds)
    const nextLayout = loadLayoutPrefs(layoutKey)
    setVisibleIds(nextPrefs?.visible?.length ? nextPrefs.visible : defaultVisible)
    if (!isLayoutControlled) {
      setWrapCellsInternal(nextLayout.wrap)
      setCenterCellsInternal(nextLayout.center)
    }
    setWidths(nextPrefs ? nextPrefs.widths : {})
  }, [gridId, columnIds, defaultVisible, layoutKey, isLayoutControlled])

  useEffect(() => {
    if (isLoadingRef.current) {
      isLoadingRef.current = false
      return
    }
    savePrefs(gridId, { visible: visibleIds, widths })
  }, [gridId, visibleIds, widths])

  useEffect(() => {
    if (isLayoutControlled) return
    if (isLoadingRef.current) return
    saveLayoutPrefs(layoutKey, { wrap: wrapCellsInternal, center: centerCellsInternal })
  }, [layoutKey, wrapCellsInternal, centerCellsInternal, isLayoutControlled])

  const tanstackColumns = useMemo(
    () => columns.map((col) => ({
      id: col.id,
      accessorFn: (row) => sortValueForColumn(col, row),
      enableSorting: col.sortable !== false,
      sortingFn: (rowA, rowB) => compareSortValues(
        sortValueForColumn(col, rowA.original),
        sortValueForColumn(col, rowB.original),
      ),
      meta: col,
    })),
    [columns],
  )

  const table = useReactTable({
    data: rows,
    columns: tanstackColumns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const displayRows = useMemo(
    () => table.getRowModel().rows.map((r) => r.original),
    [table, rows, sorting],
  )

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
    e.stopPropagation()
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
      return columnIds.filter((c) => prev.includes(c) || c === id)
    })
  }

  function toggleSort(colId) {
    setSorting((prev) => {
      const current = prev[0]
      if (!current || current.id !== colId) return [{ id: colId, desc: false }]
      if (!current.desc) return [{ id: colId, desc: true }]
      return []
    })
  }

  function sortIcon(colId) {
    const current = sorting[0]
    if (!current || current.id !== colId) {
      return <ArrowUpDown size={12} className="data-grid-sort-icon" aria-hidden />
    }
    return current.desc
      ? <ArrowDown size={12} className="data-grid-sort-icon data-grid-sort-icon--active" aria-hidden />
      : <ArrowUp size={12} className="data-grid-sort-icon data-grid-sort-icon--active" aria-hidden />
  }

  const colStyle = (col) => {
    const w = widths[col.id]
    if (w) {
      return {
        width: `${w}px`,
        minWidth: `${w}px`,
      }
    }
    return {
      width: col.width ? `${col.width}px` : undefined,
      minWidth: col.minWidth ? `${col.minWidth}px` : '72px',
    }
  }

  const cellStyle = (col) => ({
    textAlign: centerCells ? 'center' : (col.align || 'left'),
    whiteSpace: wrapCells ? 'normal' : 'nowrap',
    overflow: wrapCells ? 'visible' : 'hidden',
    textOverflow: wrapCells ? 'clip' : 'ellipsis',
    wordBreak: wrapCells ? 'break-word' : 'normal',
    verticalAlign: 'top',
  })

  const rootClass = ['data-grid', className].filter(Boolean).join(' ')

  return (
    <div className={rootClass}>
      <div className="data-grid-toolbar">
        <div className="data-grid-toolbar-left">
          <button
            type="button"
            className="admin-btn admin-btn-ghost data-grid-btn"
            onClick={() => setShowColumns((v) => !v)}
          >
            Columns ({visibleColumns.length}/{columns.length})
          </button>
          {showColumns && (
            <div className="data-grid-col-picker" role="group" aria-label="Visible columns">
              {columns.map((c) => (
                <Checkbox
                  key={c.id}
                  id={`${gridId}-col-${c.id}`}
                  checked={visibleIds.includes(c.id)}
                  onCheckedChange={() => toggleColumn(c.id)}
                  label={c.label}
                  className="data-grid-col-option"
                />
              ))}
            </div>
          )}
          {showLayoutToggles && (
            <>
              <Checkbox
                id={`${gridId}-wrap`}
                checked={wrapCells}
                onCheckedChange={setWrapCellsInternal}
                label="Wrap"
                className="data-grid-toggle"
              />
              <Checkbox
                id={`${gridId}-center`}
                checked={centerCells}
                onCheckedChange={setCenterCellsInternal}
                label="Center"
                className="data-grid-toggle"
              />
            </>
          )}
        </div>
        {toolbarExtra}
      </div>

      <div className="data-grid-scroll">
        <table className={tableClassName}>
          <colgroup>
            {visibleColumns.map((col) => (
              <col key={col.id} style={colStyle(col)} />
            ))}
          </colgroup>
          <thead className={stickyHeader ? undefined : 'data-grid-thead-static'}>
            <tr>
              {visibleColumns.map((col) => {
                const sortable = col.sortable !== false
                return (
                  <th
                    key={col.id}
                    className="data-grid-th"
                    style={cellStyle(col)}
                    title={col.label}
                    aria-sort={
                      sorting[0]?.id === col.id
                        ? (sorting[0].desc ? 'descending' : 'ascending')
                        : (sortable ? 'none' : undefined)
                    }
                  >
                    {sortable ? (
                      <button
                        type="button"
                        className="data-grid-sort-btn"
                        onClick={() => toggleSort(col.id)}
                      >
                        <span className="data-grid-th-label">{col.label}</span>
                        {sortIcon(col.id)}
                      </button>
                    ) : (
                      <span className="data-grid-th-label">{col.label}</span>
                    )}
                    <span
                      className="data-grid-resize-handle"
                      role="separator"
                      aria-orientation="vertical"
                      aria-label={`Resize ${col.label} column`}
                      onMouseDown={(e) => startResize(col.id, e)}
                    />
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {displayRows.length === 0 && (
              <tr>
                <td colSpan={visibleColumns.length} className="admin-empty">{emptyMessage}</td>
              </tr>
            )}
            {displayRows.map((row, index) => (
              <tr
                key={rowKey(row, index)}
                className={onRowClick ? 'data-grid-row-clickable' : undefined}
                aria-selected={activeRowKey != null && rowKey(row, index) === activeRowKey ? true : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {visibleColumns.map((col) => (
                  <td
                    key={col.id}
                    style={cellStyle(col)}
                    title={typeof col.title === 'function' ? col.title(row) : (col.title || undefined)}
                  >
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
