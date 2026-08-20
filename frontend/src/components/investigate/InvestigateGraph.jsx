import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchInvestigationRelationships, resolveInvestigation } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import AsyncState from '../ui/AsyncState.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import { useInvestigationOptional, INV_TYPES, INV_SOURCES } from '../../context/InvestigationContext.jsx'
import {
  canExpandEntityType,
  heuristicCveIds,
  neighborIds,
} from '../../utils/investigateGraphFilters.js'
import {
  emptyGraphState,
  INVESTIGATE_GRAPH_MAX_EDGES,
  INVESTIGATE_GRAPH_MAX_NODES,
  mergeGraphPage,
} from '../../utils/investigateGraphMerge.js'
import {
  DEFAULT_VIEW,
  computeFitView,
  computePointCloudBounds,
  truncateNodeLabel,
  zoomAtCursor,
} from '../../utils/architectureGraphView.js'
import { seedPositions, stepForce } from '../../utils/investigateForceLayout.js'
import './InvestigateGraph.css'

const EDGE_STROKE = {
  direct_fact: 'var(--text-primary, var(--text))',
  reported: 'var(--accent-primary, var(--c-accent))',
  derived: 'var(--text-secondary, var(--text2))',
  analyst_assertion: 'var(--status-warning, var(--severity-high))',
  semantic: 'var(--text-muted, var(--text3))',
}

const NODE_R = 8
const NODE_R_ACTIVE = 11

function hitRadius(scale) {
  return Math.min(24, Math.max(8, 12 / scale))
}

function shouldShowLabel(node, { selectedId, hoveredId, findLower, scale, rootId }) {
  if (node.node_id === rootId || node.node_id === selectedId || node.node_id === hoveredId) return true
  if (findLower && (node.label || '').toLowerCase().includes(findLower)) return true
  if (node.entity_type !== 'cve' && scale >= 1.25) return true
  return scale >= 2
}

function hexPoints(cx, cy, r) {
  return Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI / 3) * i - Math.PI / 6
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
  }).join(' ')
}

function baseNodeRadius(node, heuristicIds, rootId) {
  if (heuristicIds.has(node.node_id)) return 6
  if (node.node_id === rootId) return NODE_R + 3
  return NODE_R
}

function nodeDotRadius(node, active, heuristicIds, rootId) {
  return active ? NODE_R_ACTIVE : baseNodeRadius(node, heuristicIds, rootId)
}

function looksResolvable(q) {
  const t = q.trim()
  if (/^CVE-\d{4}-\d{4,}$/i.test(t)) return true
  if (/^T\d{4}(?:\.\d{3})?$/i.test(t)) return true
  if (/^camp_[0-9a-f]{12}$/i.test(t)) return true
  if (/^[0-9a-f]{32}$|^[0-9a-f]{40}$|^[0-9a-f]{64}$/i.test(t)) return true
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(t)) return true
  if (t.includes('.') && !t.includes(' ') && t.length >= 4 && !/^CVE-/i.test(t)) return true
  return false
}

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

function renderNodeShape(node, cx, cy, active, expanding, heuristicIds, rootId) {
  const r = nodeDotRadius(node, active, heuristicIds, rootId)
  const fill = active ? 'var(--accent-selected)' : 'var(--surface-raised, var(--bg2))'
  const stroke = active ? 'var(--accent-selected)' : 'var(--border-active, var(--border2))'
  const strokeWidth = expanding ? 3 : 1.5

  if (node.entity_type === 'cve') {
    return (
      <circle
        className="investigate-node-dot"
        cx={cx}
        cy={cy}
        r={r}
        fill={fill}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
    )
  }
  if (node.entity_type === 'ioc') {
    const side = r * 1.4
    const half = side / 2
    return (
      <rect
        className="investigate-node-dot"
        x={cx - half}
        y={cy - half}
        width={side}
        height={side}
        transform={`rotate(45 ${cx} ${cy})`}
        fill={fill}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
    )
  }
  if (node.entity_type === 'campaign') {
    return (
      <polygon
        className="investigate-node-dot"
        points={hexPoints(cx, cy, r)}
        fill={fill}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
    )
  }
  if (node.entity_type === 'technique' || node.entity_type === 'sigma' || node.entity_type === 'publication') {
    return (
      <rect
        className="investigate-node-dot"
        x={cx - r}
        y={cy - r * 0.75}
        width={r * 2}
        height={r * 1.5}
        rx={2}
        fill={fill}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
    )
  }
  return (
    <circle
      className="investigate-node-dot"
      cx={cx}
      cy={cy}
      r={r}
      fill={fill}
      stroke={stroke}
      strokeWidth={strokeWidth}
    />
  )
}

export default function InvestigateGraph({ onOpenCve, isActive = true, watchlist }) {
  const investigation = useInvestigationOptional()
  const [query, setQuery] = useState('')
  const [graph, setGraph] = useState(emptyGraphState)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [emptyTitle, setEmptyTitle] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [hoveredId, setHoveredId] = useState(null)
  const [positions, setPositions] = useState([])
  const [expandingId, setExpandingId] = useState(null)
  const [view, setView] = useState(() => ({ ...DEFAULT_VIEW }))
  const viewRef = useRef(view)
  viewRef.current = view
  const userMovedRef = useRef(false)
  const dragRef = useRef(null)
  const canvasRef = useRef(null)
  const sizeRef = useRef({ width: 800, height: 560 })
  const positionsRef = useRef([])
  const graphRef = useRef(graph)
  const searchGenRef = useRef(0)
  graphRef.current = graph
  positionsRef.current = positions

  useEffect(() => {
    userMovedRef.current = false
  }, [graph.root_id])

  useEffect(() => {
    const el = canvasRef.current
    if (!el) return undefined
    const handler = (e) => {
      e.preventDefault()
      userMovedRef.current = true
      const rect = el.getBoundingClientRect()
      const cursorX = e.clientX - rect.left
      const cursorY = e.clientY - rect.top
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
      setView((v) => zoomAtCursor(v, cursorX, cursorY, factor))
    }
    el.addEventListener('wheel', handler, { passive: false })
    return () => el.removeEventListener('wheel', handler)
  }, [graph.root_id])

  const fitGraphToView = useCallback(() => {
    const el = canvasRef.current
    const pos = positionsRef.current
    if (!el || !pos.length) return
    const bounds = computePointCloudBounds(pos, 12, 48)
    setView(computeFitView(bounds, el.clientWidth, el.clientHeight))
  }, [])

  const zoomFromButton = useCallback((factor) => {
    const el = canvasRef.current
    if (!el) return
    userMovedRef.current = true
    setView((v) => zoomAtCursor(v, el.clientWidth / 2, el.clientHeight / 2, factor))
  }, [])

  const onPointerDown = useCallback((e) => {
    if (e.target.closest('[data-node-id]')) return
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      origin: view,
      panning: false,
    }
    e.currentTarget.setPointerCapture(e.pointerId)
  }, [view])

  const onPointerMove = useCallback((e) => {
    if (!dragRef.current) return
    const { startX, startY, origin } = dragRef.current
    const dx = e.clientX - startX
    const dy = e.clientY - startY
    if (Math.hypot(dx, dy) >= 4) {
      dragRef.current.panning = true
    }
    if (!dragRef.current.panning) return
    userMovedRef.current = true
    setView({
      ...origin,
      x: origin.x + dx,
      y: origin.y + dy,
    })
  }, [])

  const onPointerUp = useCallback((e) => {
    if (dragRef.current) {
      const { panning } = dragRef.current
      if (!panning && !e.target.closest('[data-node-id]')) {
        setSelectedId(null)
      }
    }
    dragRef.current = null
    if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
  }, [])

  const onNodeClick = useCallback((node) => {
    setSelectedId((id) => (id === node.node_id ? null : node.node_id))
  }, [])

  const onCanvasKeyDown = useCallback((e) => {
    if (e.target.closest('input, textarea')) return
    const el = canvasRef.current
    if (!el) return
    if (e.key === '+' || e.key === '=') {
      e.preventDefault()
      zoomFromButton(1.1)
    } else if (e.key === '-' || e.key === '_') {
      e.preventDefault()
      zoomFromButton(1 / 1.1)
    } else if (e.key === '0') {
      e.preventDefault()
      userMovedRef.current = false
      fitGraphToView()
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      userMovedRef.current = true
      setView((v) => ({ ...v, x: v.x + 40 }))
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      userMovedRef.current = true
      setView((v) => ({ ...v, x: v.x - 40 }))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      userMovedRef.current = true
      setView((v) => ({ ...v, y: v.y + 40 }))
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      userMovedRef.current = true
      setView((v) => ({ ...v, y: v.y - 40 }))
    }
  }, [fitGraphToView, zoomFromButton])

  const positionById = useMemo(
    () => new Map(positions.map((node) => [node.node_id, node])),
    [positions],
  )

  const selected = useMemo(
    () => graph.nodes.find((node) => node.node_id === selectedId) || null,
    [graph.nodes, selectedId],
  )

  const runSearch = useCallback(async (raw) => {
    const q = (raw || '').trim()
    if (!q) return
    const generation = searchGenRef.current + 1
    searchGenRef.current = generation
    setLoading(true)
    setError(null)
    setEmptyTitle('')
    try {
      const resolved = await resolveInvestigation(q)
      if (generation !== searchGenRef.current) return
      const root = resolved?.root
      if (!root?.entity_type || !root?.entity_id) {
        setGraph(emptyGraphState())
        setEmptyTitle('Could not resolve that query.')
        return
      }
      const page = await fetchInvestigationRelationships(root.entity_type, root.entity_id)
      if (generation !== searchGenRef.current) return
      const merged = mergeGraphPage(emptyGraphState(), page)
      setGraph(merged)
      setSelectedId(root.node_id)
    } catch (err) {
      if (generation !== searchGenRef.current) return
      if (err?.status === 404) {
        setGraph(emptyGraphState())
        setEmptyTitle('Unknown entity — BRIEFR has no local graph for that query.')
        setError(null)
        return
      }
      setError(err)
      notifyApiError(err)
    } finally {
      if (generation === searchGenRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const handle = setTimeout(() => {
      const q = query.trim()
      if (!looksResolvable(q)) return
      runSearch(q)
    }, 400)
    return () => clearTimeout(handle)
  }, [query, runSearch])

  const expandNode = useCallback(async (node) => {
    if (!node?.entity_type || !node?.entity_id) return
    setExpandingId(node.node_id)
    setError(null)
    try {
      const page = await fetchInvestigationRelationships(node.entity_type, node.entity_id)
      setGraph((prev) => mergeGraphPage(prev, page))
      setSelectedId(node.node_id)
    } catch (err) {
      if (err?.status === 404) {
        setError(new Error('No relationships stored for this node.'))
        return
      }
      setError(err)
      notifyApiError(err)
    } finally {
      setExpandingId(null)
    }
  }, [])

  const onNodeDoubleClick = useCallback((node) => {
    if (!canExpandEntityType(node.entity_type)) return
    expandNode(node)
  }, [expandNode])

  const focusId = hoveredId || selectedId
  const findLower = query.trim().toLowerCase()
  const heuristicIds = useMemo(() => heuristicCveIds(graph), [graph])
  const highlightedNodeIds = useMemo(() => {
    if (!focusId) return null
    const ids = new Set(neighborIds(graph, focusId))
    ids.add(focusId)
    if (graph.root_id) ids.add(graph.root_id)
    return ids
  }, [focusId, graph])

  useEffect(() => {
    const el = canvasRef.current
    if (!el) return undefined
    const measure = () => {
      const width = Math.max(el.clientWidth, 320)
      const height = Math.max(el.clientHeight, 360)
      sizeRef.current = { width, height }
      const prior = new Map(positionsRef.current.map((node) => [node.node_id, node]))
      setPositions(seedPositions(
        graphRef.current.nodes,
        width,
        height,
        prior,
        graphRef.current.root_id,
      ))
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [graph.nodes])

  useEffect(() => {
    if (!isActive || graph.nodes.length === 0) return undefined
    const reduced = prefersReducedMotion()
    let frame = 0
    let ticks = 0
    const maxTicks = reduced ? 12 : 180
    const rootId = graph.root_id
    const loop = () => {
      const { width, height } = sizeRef.current
      const stepped = stepForce(
        positionsRef.current,
        graphRef.current.edges,
        width,
        height,
        rootId,
      )
      positionsRef.current = stepped
      ticks += 1
      setPositions(stepped)
      if (ticks < maxTicks) {
        frame = requestAnimationFrame(loop)
      } else if (!userMovedRef.current) {
        fitGraphToView()
      }
    }
    frame = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(frame)
  }, [isActive, graph.nodes, graph.edges, graph.root_id, fitGraphToView])

  const pinNode = useCallback((node) => {
    if (!investigation || !node) return
    if (node.entity_type === 'cve') {
      investigation.ensureCveInThread(node.entity_id, INV_SOURCES.DRAWER)
      return
    }
    if (node.entity_type === 'ioc') {
      investigation.recordIocPivot(node.label || node.entity_id)
      return
    }
    if (node.entity_type === 'technique') {
      investigation.recordItem({
        type: INV_TYPES.TECHNIQUE,
        id: node.entity_id,
        title: node.label || node.entity_id,
        source: INV_SOURCES.DRAWER,
      })
      return
    }
    investigation.recordItem({
      type: node.entity_type,
      id: node.entity_id,
      title: node.label || node.entity_id,
      source: INV_SOURCES.DRAWER,
    })
  }, [investigation])

  const idle = !loading && graph.nodes.length === 0 && !error && !emptyTitle
  const showHonesty = graph.nodes.length > 0
    && (graph.truncated || graph.capped || graph.source_status === 'degraded'
      || graph.knowledge_state === 'stale' || graph.knowledge_state === 'partial')

  return (
    <div className="investigate-page">
      <header className="investigate-hero">
        <h1 className="investigate-hero-title mono">INVESTIGATE</h1>
        <p className="investigate-hero-copy">
          Graph browser over stored CVE, IOC, technique, and publication hops. Search once, expand nodes to pivot like an Obsidian map — no live enrichment on each click.
        </p>
      </header>

      <form
        className="investigate-toolbar control-toolbar--fields"
        onSubmit={(event) => {
          event.preventDefault()
          runSearch(query)
        }}
      >
        <label className="control-field">
          <span className="control-field-label">SEARCH</span>
          <input
            className="investigate-search mono"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="CVE, IP, hash, domain, technique…"
            aria-label="Investigate graph search"
            autoComplete="off"
          />
        </label>
        <button type="submit" className="investigate-search-btn mono" disabled={loading || !query.trim()}>
          {loading ? 'RESOLVING…' : 'RESOLVE'}
        </button>
      </form>

      <p className="investigate-hint mono">
        Scroll to zoom · drag to pan · click to inspect · double-click to expand. Edges encode evidence class, not certainty.
      </p>

      {showHonesty && (
        <div className="investigate-honesty mono" role="status">
          {graph.capped
            ? `Canvas capped at ${INVESTIGATE_GRAPH_MAX_NODES} nodes / ${INVESTIGATE_GRAPH_MAX_EDGES} edges — expand a focused node instead of widening everything. `
            : ''}
          {graph.truncated ? 'Truncated — more hops exist than this page returned. ' : ''}
          {graph.source_status === 'degraded' ? 'Source status degraded. ' : ''}
          {graph.knowledge_state === 'stale' ? 'Knowledge is stale. ' : ''}
          {graph.knowledge_state === 'partial' ? 'Partial neighborhood.' : ''}
        </div>
      )}

      <div className="investigate-stage">
        <div
          className="investigate-canvas"
          ref={canvasRef}
          tabIndex={0}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
          onKeyDown={onCanvasKeyDown}
          aria-label="Investigation graph canvas"
        >
          <AsyncState
            loading={loading && graph.nodes.length === 0}
            error={error}
            onRetry={() => runSearch(query)}
            empty={Boolean(emptyTitle) && graph.nodes.length === 0}
            emptyTitle={emptyTitle}
            data={graph.nodes.length ? graph : null}
            skeleton={<div className="investigate-skeleton" aria-hidden="true" />}
          >
            {idle && (
              <EmptyState title="Search a CVE, hash, IP, or domain to open the investigation graph." />
            )}
            {graph.nodes.length > 0 && (
              <svg
                className="investigate-svg"
                width="100%"
                height="100%"
                role="img"
                aria-label="Investigation relationship graph"
              >
                <g
                  className="investigate-svg-scene"
                  transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}
                >
                  {graph.edges.map((edge) => {
                    const source = positionById.get(edge.source_node_id)
                    const target = positionById.get(edge.target_node_id)
                    if (!source || !target) return null
                    const dashed = edge.edge_class === 'semantic'
                    const edgeDimmed = Boolean(focusId)
                      && edge.source_node_id !== focusId
                      && edge.target_node_id !== focusId
                    return (
                      <line
                        key={edge.edge_id}
                        x1={source.x}
                        y1={source.y}
                        x2={target.x}
                        y2={target.y}
                        stroke={EDGE_STROKE[edge.edge_class] || 'var(--text-muted, var(--text3))'}
                        strokeWidth={edge.edge_class === 'direct_fact' ? 2 : 1.25}
                        strokeDasharray={dashed ? '4 3' : undefined}
                        opacity={edgeDimmed ? 0.2 : 0.85}
                      />
                    )
                  })}
                  {positions.map((node) => {
                    const active = node.node_id === selectedId
                    const expanding = node.node_id === expandingId
                    const dimmed = Boolean(highlightedNodeIds) && !highlightedNodeIds.has(node.node_id)
                    const showLabel = shouldShowLabel(node, {
                      selectedId,
                      hoveredId,
                      findLower,
                      scale: view.scale,
                      rootId: graph.root_id,
                    })
                    const dotR = nodeDotRadius(node, active, heuristicIds, graph.root_id)
                    const pinned = watchlist?.getState(node.entity_id) === 'pin'
                    const inThread = investigation?.isCveInThread?.(node.entity_id)
                    return (
                      <g
                        key={node.node_id}
                        data-node-id={node.node_id}
                        className={[
                          'investigate-node',
                          dimmed ? 'investigate-node-dim' : '',
                        ].filter(Boolean).join(' ')}
                        onClick={() => onNodeClick(node)}
                        onDoubleClick={() => onNodeDoubleClick(node)}
                        onMouseEnter={() => setHoveredId(node.node_id)}
                        onMouseLeave={() => setHoveredId(null)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' && event.shiftKey) {
                            event.preventDefault()
                            onNodeDoubleClick(node)
                          } else if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            onNodeClick(node)
                          }
                        }}
                        tabIndex={0}
                        role="button"
                        aria-pressed={active}
                        aria-label={`${node.entity_type} ${node.label}`}
                      >
                        <circle
                          className="investigate-node-hit"
                          cx={node.x}
                          cy={node.y}
                          r={hitRadius(view.scale)}
                        />
                        {inThread && (
                          <circle
                            className="investigate-node-thread"
                            cx={node.x}
                            cy={node.y}
                            r={dotR + 5}
                            fill="none"
                            stroke="var(--accent-primary, var(--c-accent))"
                            strokeWidth={1.25}
                            strokeDasharray="3 2"
                          />
                        )}
                        {renderNodeShape(node, node.x, node.y, active, expanding, heuristicIds, graph.root_id)}
                        {pinned && (
                          <polygon
                            className="investigate-node-pin"
                            points={`${node.x},${node.y - dotR - 6} ${node.x - 4},${node.y - dotR - 2} ${node.x + 4},${node.y - dotR - 2}`}
                            fill="none"
                            stroke="var(--accent-primary, var(--c-accent))"
                            strokeWidth={1.5}
                          />
                        )}
                        {showLabel && (
                          <text
                            x={node.x}
                            y={node.y + 22}
                            textAnchor="middle"
                            className="investigate-node-label"
                          >
                            {truncateNodeLabel(node.label || node.entity_id || '', 28)}
                          </text>
                        )}
                      </g>
                    )
                  })}
                </g>
              </svg>
            )}
          </AsyncState>
          {graph.nodes.length > 0 && (
            <div className="investigate-camera-tools">
              <button type="button" aria-label="Zoom in" onClick={() => zoomFromButton(1.1)}>+</button>
              <button type="button" aria-label="Zoom out" onClick={() => zoomFromButton(1 / 1.1)}>−</button>
              <button
                type="button"
                aria-label="Fit graph"
                onClick={() => {
                  userMovedRef.current = false
                  fitGraphToView()
                }}
              >
                FIT GRAPH
              </button>
              <button
                type="button"
                aria-label="Reset view"
                onClick={() => {
                  userMovedRef.current = false
                  fitGraphToView()
                }}
              >
                RESET VIEW
              </button>
            </div>
          )}
        </div>

        <aside className="investigate-inspector" aria-label="Selected node">
          <h2 className="investigate-inspector-title mono">NODE</h2>
          {!selected && <p className="investigate-inspector-empty">Select a node to inspect evidence class and pin it to the session thread.</p>}
          {selected && (
            <>
              <dl className="investigate-meta">
                <div>
                  <dt>Type</dt>
                  <dd className="mono">{selected.entity_type}</dd>
                </div>
                <div>
                  <dt>Id</dt>
                  <dd className="mono">{selected.entity_id}</dd>
                </div>
                <div>
                  <dt>Knowledge</dt>
                  <dd className="mono">{selected.knowledge_state || 'known'}</dd>
                </div>
              </dl>
              <div className="investigate-inspector-actions">
                <button type="button" className="investigate-search-btn mono" onClick={() => expandNode(selected)} disabled={expandingId === selected.node_id}>
                  EXPAND
                </button>
                {investigation && (
                  <button type="button" className="investigate-ghost-btn mono" onClick={() => pinNode(selected)}>
                    PIN THREAD
                  </button>
                )}
                {selected.entity_type === 'cve' && onOpenCve && (
                  <button type="button" className="investigate-ghost-btn mono" onClick={() => onOpenCve(selected.entity_id)}>
                    OPEN CVE
                  </button>
                )}
              </div>
            </>
          )}
          <h3 className="investigate-inspector-title mono">EDGE CLASS</h3>
          <ul className="investigate-legend">
            <li><span className="investigate-swatch investigate-swatch--direct" /> direct_fact</li>
            <li><span className="investigate-swatch investigate-swatch--reported" /> reported</li>
            <li><span className="investigate-swatch investigate-swatch--derived" /> derived</li>
            <li><span className="investigate-swatch investigate-swatch--assertion" /> analyst_assertion</li>
            <li><span className="investigate-swatch investigate-swatch--semantic" /> semantic (opt-in)</li>
          </ul>
        </aside>
      </div>
    </div>
  )
}
