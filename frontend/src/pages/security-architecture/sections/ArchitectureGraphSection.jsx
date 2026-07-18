import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchSecurityArchitectureGraph } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import {
  COL_WIDTH,
  computeGraphLayout,
} from '../../../utils/architectureGraphLayout.js'
import {
  DEFAULT_VIEW,
  computeFitView,
  computeGraphBounds,
  truncateNodeLabel,
  zoomAtCursor,
} from '../../../utils/architectureGraphView.js'

const FILTER_ALL = 'all'
const NODE_W = 240
const NODE_H = 26

/**
 * System Architecture graph (spec §5.2, §8 TM-4): interactive pan/zoom
 * render of the generated `graphs/architecture.json`.
 *
 * No content-sized SVG viewBox — pan/zoom transform works in CSS pixels so
 * fit-to-view math stays 1:1 with the canvas (avoids double-scale / wrong zoom).
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
  const [view, setView] = useState(() => ({ ...DEFAULT_VIEW }))

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
  const { positioned, byId, clusters } = layout

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

  const focusId = hoveredId || selectedNodeId

  const connectedEdgeIds = useMemo(() => {
    if (!focusId || !graph) return new Set()
    return new Set(
      graph.edges.filter(e => e.source === focusId || e.target === focusId).map(e => e.id),
    )
  }, [focusId, graph])

  const fitGraphToView = useCallback(() => {
    const el = canvasRef.current
    if (!el || !visibleNodes.length) return
    const width = el.clientWidth
    const height = el.clientHeight
    if (width <= 0 || height <= 0) return
    // Fit only what is on screen (cluster/search filters) so zoom is not
    // forced by off-filter columns.
    const bounds = computeGraphBounds(visibleNodes)
    setView(computeFitView(bounds, width, height))
  }, [visibleNodes])

  useEffect(() => {
    if (!graph || !visibleNodes.length) return undefined
    const frame = requestAnimationFrame(() => fitGraphToView())
    return () => cancelAnimationFrame(frame)
  }, [graph, visibleNodes.length, clusterFilter, searchLower, fitGraphToView])

  useEffect(() => {
    const el = canvasRef.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    let frame = 0
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => fitGraphToView())
    })
    ro.observe(el)
    return () => {
      cancelAnimationFrame(frame)
      ro.disconnect()
    }
  }, [graph, fitGraphToView])

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

  const resetView = useCallback(() => {
    fitGraphToView()
  }, [fitGraphToView])

  const clusterIndex = useMemo(() => {
    const map = new Map()
    clusters.forEach((c, i) => map.set(c.id, i))
    return map
  }, [clusters])

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
          <svg width="100%" height="100%" role="img" aria-label="System architecture graph">
            <g
              className="sa-graph-scene"
              transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}
            >
              {clusters.map((c) => {
                if (clusterFilter !== FILTER_ALL && c.id !== clusterFilter) return null
                const ci = clusterIndex.get(c.id) ?? 0
                return (
                  <text
                    key={c.id}
                    x={ci * COL_WIDTH + 20}
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
                // Only draw links for the focused node — avoids overlapping spaghetti.
                if (focusId && !highlighted) return null
                if (!focusId) return null
                return (
                  <line
                    key={e.id}
                    x1={s.x + NODE_W} y1={s.y + NODE_H / 2}
                    x2={t.x} y2={t.y + NODE_H / 2}
                    className="sa-graph-edge sa-graph-edge-active"
                  />
                )
              })}
              {visibleNodes.map(node => {
                const selected = node.id === selectedNodeId
                const matched = searchLower && node.label?.toLowerCase().includes(searchLower)
                const dimmed = Boolean(focusId)
                  && focusId !== node.id
                  && !graph?.edges.some(
                    e => (e.source === focusId && e.target === node.id)
                      || (e.target === focusId && e.source === node.id),
                  )
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
                      dimmed ? 'sa-graph-node-dim' : '',
                    ].filter(Boolean).join(' ')}
                    onClick={() => {
                      if (selected) onClearSelection()
                      else onSelectNode(node.id)
                    }}
                    onMouseEnter={() => setHoveredId(node.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    tabIndex={0}
                    role="button"
                    aria-pressed={selected}
                    aria-label={`${node.kind} ${node.label}`}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        if (selected) onClearSelection()
                        else onSelectNode(node.id)
                      }
                    }}
                  >
                    <rect width={NODE_W} height={NODE_H} rx={2} />
                    <text x={8} y={NODE_H / 2 + 4}>
                      <title>{node.label}</title>
                      {truncateNodeLabel(node.label)}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>
        </div>
        <p className="sa-graph-hint mono">
          Click a node to select · click again to deselect · hover/select shows links ·
          scroll to zoom · drag to pan · edges are SQL refs (incl. via db helpers /
          called modules) and curated job→external links
        </p>
      </AsyncState>
    </div>
  )
}
