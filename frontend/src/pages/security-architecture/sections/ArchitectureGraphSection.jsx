import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchSecurityArchitectureGraph } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import ContextRail from '../ContextRail.jsx'
import {
  computeGraphLayout,
} from '../../../utils/architectureGraphLayout.js'
import {
  DEFAULT_VIEW,
  computeFitView,
  computeGraphBounds,
  zoomAtCursor,
} from '../../../utils/architectureGraphView.js'

const FILTER_ALL = 'all'
const NODE_W = 260
const NODE_H = 26

/**
 * System Architecture graph (spec §5.2, §8 TM-4): interactive pan/zoom
 * render of the generated `graphs/architecture.json`.
 */
export default function ArchitectureGraphSection({
  selectedNodeId,
  onSelectNode,
  onClearSelection,
}) {
  const [graph, setGraph] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [clusterFilter, setClusterFilter] = useState(FILTER_ALL)
  const [search, setSearch] = useState('')
  const [hoveredId, setHoveredId] = useState(null)
  const [view, setView] = useState({ ...DEFAULT_VIEW })

  const canvasRef = useRef(null)
  const dragRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureGraph()
      .then(res => { if (!cancelled) setGraph(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [reloadKey])

  const layout = useMemo(() => computeGraphLayout(graph), [graph])
  const { positioned, byId, clusters, viewWidth, viewHeight } = layout

  const searchLower = search.trim().toLowerCase()
  const isHidden = useCallback((node) => {
    if (clusterFilter !== FILTER_ALL && node.cluster !== clusterFilter) return true
    if (searchLower && !node.label?.toLowerCase().includes(searchLower)) return true
    return false
  }, [clusterFilter, searchLower])

  const visibleNodes = useMemo(
    () => positioned.filter(node => !isHidden(node)),
    [positioned, isHidden],
  )

  const visibleNodeIds = useMemo(
    () => new Set(visibleNodes.map(node => node.id)),
    [visibleNodes],
  )

  const connectedEdgeIds = useMemo(() => {
    const activeId = hoveredId || selectedNodeId
    if (!activeId || !graph) return new Set()
    return new Set(
      graph.edges.filter(e => e.source === activeId || e.target === activeId).map(e => e.id),
    )
  }, [hoveredId, selectedNodeId, graph])

  const fitGraphToView = useCallback(() => {
    const el = canvasRef.current
    if (!el || !positioned.length) return
    const bounds = computeGraphBounds(positioned)
    setView(computeFitView(bounds, el.clientWidth, el.clientHeight))
  }, [positioned])

  useEffect(() => {
    if (!graph || !positioned.length) return undefined
    const frame = requestAnimationFrame(() => fitGraphToView())
    return () => cancelAnimationFrame(frame)
  }, [graph, positioned.length, fitGraphToView])

  useEffect(() => {
    const el = canvasRef.current
    if (!el) return undefined
    const handler = (e) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const cursorX = e.clientX - rect.left
      const cursorY = e.clientY - rect.top
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
      setView(v => zoomAtCursor(v, cursorX, cursorY, factor))
    }
    el.addEventListener('wheel', handler, { passive: false })
    return () => el.removeEventListener('wheel', handler)
  }, [graph])

  const onPointerDown = useCallback((e) => {
    if (e.target.closest('[data-node]')) return
    dragRef.current = { startX: e.clientX, startY: e.clientY, origin: view }
    e.currentTarget.setPointerCapture(e.pointerId)
  }, [view])

  const onPointerMove = useCallback((e) => {
    if (!dragRef.current) return
    const { startX, startY, origin } = dragRef.current
    setView(v => ({ ...v, x: origin.x + (e.clientX - startX), y: origin.y + (e.clientY - startY) }))
  }, [])

  const onPointerUp = useCallback((e) => {
    dragRef.current = null
    if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
  }, [])

  const resetView = useCallback(() => setView({ ...DEFAULT_VIEW }), [])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">SYSTEM ARCHITECTURE</h2>
        {graph && (
          <p className="sa-mitre-counts mono">
            {graph.nodes.length} nodes · {graph.edges.length} edges (generated)
          </p>
        )}
      </div>

      <div className="sa-graph-toolbar">
        <div className="sa-type-tabs mono" role="tablist" aria-label="Cluster filter">
          <button
            type="button" role="tab" aria-selected={clusterFilter === FILTER_ALL}
            className={`sa-type-tab${clusterFilter === FILTER_ALL ? ' active' : ''}`}
            onClick={() => setClusterFilter(FILTER_ALL)}
          >
            ALL
          </button>
          {clusters.map(c => (
            <button
              key={c.id} type="button" role="tab" aria-selected={clusterFilter === c.id}
              className={`sa-type-tab${clusterFilter === c.id ? ' active' : ''}`}
              onClick={() => setClusterFilter(c.id)}
            >
              {c.label.toUpperCase()}
            </button>
          ))}
        </div>
        <input
          type="text"
          className="sa-stack-input mono sa-graph-search"
          placeholder="search nodes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search graph nodes"
        />
        <button type="button" className="admin-btn admin-btn-ghost mono" onClick={fitGraphToView}>
          FIT GRAPH
        </button>
        <button type="button" className="admin-btn admin-btn-ghost mono" onClick={resetView}>
          RESET VIEW
        </button>
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && positioned.length === 0)}
        emptyTitle={error ? undefined : 'No architecture graph yet — run scripts/generate_security_corpus.py.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <div
          className="sa-graph-canvas"
          ref={canvasRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
        >
          <svg viewBox={`0 0 ${viewWidth} ${viewHeight}`} width="100%" height="100%" role="img" aria-label="System architecture graph">
            <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
              {clusters.map((c, ci) => {
                if (clusterFilter !== FILTER_ALL && c.id !== clusterFilter) return null
                return (
                  <text
                    key={c.id}
                    x={ci * 320 + 20}
                    y={28}
                    className="sa-graph-cluster-label"
                  >
                    {c.label}
                  </text>
                )
              })}
              {graph?.edges.map(e => {
                if (!visibleNodeIds.has(e.source) || !visibleNodeIds.has(e.target)) return null
                const s = byId.get(e.source)
                const t = byId.get(e.target)
                if (!s || !t) return null
                const highlighted = connectedEdgeIds.has(e.id)
                return (
                  <line
                    key={e.id}
                    x1={s.x + NODE_W} y1={s.y + NODE_H / 2}
                    x2={t.x} y2={t.y + NODE_H / 2}
                    className={`sa-graph-edge${highlighted ? ' sa-graph-edge-active' : ''}`}
                  />
                )
              })}
              {visibleNodes.map(node => {
                const selected = node.id === selectedNodeId
                const matched = searchLower && node.label?.toLowerCase().includes(searchLower)
                return (
                  <g
                    key={node.id}
                    data-node="true"
                    transform={`translate(${node.x} ${node.y})`}
                    className={[
                      'sa-graph-node',
                      `sa-graph-node-${node.kind}`,
                      selected ? 'sa-graph-node-selected' : '',
                      matched ? 'sa-graph-node-match' : '',
                    ].filter(Boolean).join(' ')}
                    onClick={() => onSelectNode(node.id)}
                    onMouseEnter={() => setHoveredId(node.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    tabIndex={0}
                    role="button"
                    aria-pressed={selected}
                    aria-label={`${node.kind} ${node.label}`}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectNode(node.id) } }}
                  >
                    <rect width={NODE_W} height={NODE_H} rx={2} />
                    <text x={8} y={NODE_H / 2 + 4}>{node.label}</text>
                  </g>
                )
              })}
            </g>
          </svg>
        </div>
        <p className="sa-graph-hint mono">
          Scroll to zoom at cursor (0.4×–4×) · drag to pan · click a node for detail
        </p>
        {selectedNodeId && (
          <div className="sa-graph-detail" aria-label="Selected node detail">
            <ContextRail nodeId={selectedNodeId} onClose={onClearSelection} />
          </div>
        )}
      </AsyncState>
    </div>
  )
}
