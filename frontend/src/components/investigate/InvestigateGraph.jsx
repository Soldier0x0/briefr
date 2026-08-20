import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchInvestigationRelationships, resolveInvestigation } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import AsyncState from '../ui/AsyncState.jsx'
import Checkbox from '../ui/Checkbox.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import { useInvestigationOptional, INV_TYPES, INV_SOURCES } from '../../context/InvestigationContext.jsx'
import { copyToClipboard } from '../../utils/report.js'
import {
  canExpandEntityType,
  DEFAULT_EDGE_CLASSES,
  EDGE_CLASS_CHIPS,
  formatNeighborhoodMarkdown,
  heuristicCveIds,
  incidentEdges,
  neighborIds,
  otherNodeId,
  parseIocEntityId,
  relatedCveCount,
  visibleGraph,
} from '../../utils/investigateGraphFilters.js'
import {
  emptyGraphState,
  INVESTIGATE_GRAPH_MAX_EDGES,
  INVESTIGATE_GRAPH_MAX_NODES,
  investigationRelationshipParams,
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
const ENTITY_TYPE_CHIPS = ['all', 'cve', 'ioc', 'technique', 'campaign', 'publication']
const EDGE_CLASS_LABELS = {
  direct_fact: 'FACT',
  reported: 'REPORTED',
  derived: 'DERIVED',
  analyst_assertion: 'ASSERTION',
  semantic: 'SEMANTIC',
}

function hitRadius(scale) {
  return Math.min(24, Math.max(8, 12 / scale))
}

function shouldShowLabel(node, { selectedId, hoveredId, findLower, scale, rootId }) {
  if (node.node_id === rootId || node.node_id === selectedId || node.node_id === hoveredId) return true
  if (findLower && (node.label || node.entity_id || '').toLowerCase().includes(findLower)) return true
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
  if (node.entity_type === 'technique' || node.entity_type === 'sigma_rule' || node.entity_type === 'publication') {
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

export default function InvestigateGraph({
  onOpenCve,
  isActive = true,
  watchlist,
  onWatchlistChange,
  onOpenForgeCampaigns,
  onOpenAdvisories,
  initialQuery = '',
  onQueryResolved,
}) {
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
  const [showRelatedCves, setShowRelatedCves] = useState(false)
  const [entityType, setEntityType] = useState('all')
  const [edgeClasses, setEdgeClasses] = useState(() => new Set(DEFAULT_EDGE_CLASSES))
  const [isolate, setIsolate] = useState(false)
  const [findText, setFindText] = useState('')
  const [includeSemantic, setIncludeSemantic] = useState(false)
  const includeSemanticRef = useRef(includeSemantic)
  includeSemanticRef.current = includeSemantic
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
  const expandGenRef = useRef(0)
  const lastConsumedInitialQueryRef = useRef('')
  const skipDebounceRef = useRef(false)
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
    if (e.target.closest('[data-node-id], button, input, a, [role="tab"], .investigate-camera-tools, .ui-checkbox, label')) return
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

  const nodesById = useMemo(
    () => new Map(graph.nodes.map((node) => [node.node_id, node])),
    [graph.nodes],
  )

  const visible = useMemo(
    () => visibleGraph(graph, {
      showRelatedCves,
      entityType,
      edgeClasses,
      isolateNodeId: isolate ? (selectedId || graph.root_id) : null,
    }),
    [graph, showRelatedCves, entityType, edgeClasses, isolate, selectedId],
  )

  const visibleNodeIds = useMemo(
    () => new Set(visible.nodes.map((node) => node.node_id)),
    [visible.nodes],
  )

  const edgeClassesKey = useMemo(() => [...edgeClasses].sort().join(','), [edgeClasses])

  const selected = useMemo(
    () => graph.nodes.find((node) => node.node_id === selectedId) || null,
    [graph.nodes, selectedId],
  )

  const selectedIncidents = useMemo(
    () => (selectedId ? incidentEdges(graph, selectedId) : []),
    [graph, selectedId],
  )

  const runSearch = useCallback(async (raw) => {
    const q = (raw || '').trim()
    if (!q) return
    const generation = searchGenRef.current + 1
    searchGenRef.current = generation
    expandGenRef.current += 1
    setExpandingId(null)
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
      const page = await fetchInvestigationRelationships(
        root.entity_type,
        root.entity_id,
        investigationRelationshipParams(includeSemanticRef.current),
      )
      if (generation !== searchGenRef.current) return
      const merged = mergeGraphPage(emptyGraphState(), page)
      setGraph(merged)
      setSelectedId(root.node_id)
      const canonical = (resolved.query || q).trim()
      if (canonical) lastConsumedInitialQueryRef.current = canonical
      onQueryResolved?.(canonical || q)
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
  }, [onQueryResolved])

  useEffect(() => {
    const q = (initialQuery || '').trim()
    if (!q || q === lastConsumedInitialQueryRef.current) return
    lastConsumedInitialQueryRef.current = q
    skipDebounceRef.current = true
    setQuery(q)
    runSearch(q)
  }, [initialQuery, runSearch])

  useEffect(() => {
    const handle = setTimeout(() => {
      if (skipDebounceRef.current) {
        skipDebounceRef.current = false
        return
      }
      const q = query.trim()
      if (!looksResolvable(q)) return
      if (q === lastConsumedInitialQueryRef.current) return
      runSearch(q)
    }, 400)
    return () => clearTimeout(handle)
  }, [query, runSearch])

  const enableSemantic = useCallback(async () => {
    setIncludeSemantic(true)
    setEdgeClasses((prev) => {
      const next = new Set(prev)
      next.add('semantic')
      return next
    })
    if (!graph.root_id) return
    const root = graph.nodes.find((n) => n.node_id === graph.root_id)
    if (!root) return
    const generation = searchGenRef.current + 1
    searchGenRef.current = generation
    const requestedRootId = graph.root_id
    try {
      const page = await fetchInvestigationRelationships(
        root.entity_type,
        root.entity_id,
        investigationRelationshipParams(true),
      )
      if (generation !== searchGenRef.current) return
      if (graphRef.current.root_id !== requestedRootId) return
      setGraph((prev) => mergeGraphPage(prev, page))
    } catch (err) {
      if (generation !== searchGenRef.current) return
      notifyApiError(err)
    }
  }, [graph.root_id, graph.nodes])

  const expandNode = useCallback(async (node, params) => {
    if (!node?.entity_type || !node?.entity_id) return
    const generation = expandGenRef.current + 1
    expandGenRef.current = generation
    const requestedRootId = graphRef.current.root_id
    setExpandingId(node.node_id)
    setError(null)
    try {
      const page = await fetchInvestigationRelationships(
        node.entity_type,
        node.entity_id,
        investigationRelationshipParams(includeSemantic, params),
      )
      if (generation !== expandGenRef.current) return
      if (graphRef.current.root_id !== requestedRootId) return
      setGraph((prev) => mergeGraphPage(prev, page))
      setSelectedId(node.node_id)
    } catch (err) {
      if (generation !== expandGenRef.current) return
      if (err?.status === 404) {
        setError(new Error('No relationships stored for this node.'))
        return
      }
      setError(err)
      notifyApiError(err)
    } finally {
      if (generation === expandGenRef.current) setExpandingId(null)
    }
  }, [includeSemantic])

  const toggleEdgeClass = useCallback((cls) => {
    if (cls === 'semantic' && !includeSemantic) {
      void enableSemantic()
      return
    }
    setEdgeClasses((prev) => {
      const next = new Set(prev)
      if (next.has(cls)) next.delete(cls)
      else next.add(cls)
      return next
    })
  }, [enableSemantic, includeSemantic])

  const onNodeDoubleClick = useCallback((node) => {
    if (!canExpandEntityType(node.entity_type)) return
    expandNode(node)
  }, [expandNode])

  const focusId = hoveredId || selectedId
  const findLower = findText.trim().toLowerCase()
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
      const layoutNodes = visibleGraph(graphRef.current, {
        showRelatedCves,
        entityType,
        edgeClasses,
        isolateNodeId: isolate ? (selectedId || graphRef.current.root_id) : null,
      }).nodes
      setPositions(seedPositions(
        layoutNodes,
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
  }, [visible.nodes, showRelatedCves, entityType, edgeClasses, isolate, selectedId])

  useEffect(() => {
    if (!isActive || visible.nodes.length === 0) return undefined
    const reduced = prefersReducedMotion()
    let frame = 0
    let ticks = 0
    const maxTicks = reduced ? 12 : 180
    const rootId = graph.root_id
    const layoutEdges = visible.edges
    const loop = () => {
      const { width, height } = sizeRef.current
      const stepped = stepForce(
        positionsRef.current,
        layoutEdges,
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
  }, [isActive, visible, fitGraphToView, graph.root_id])

  useEffect(() => {
    if (!visible.nodes.length) return undefined
    userMovedRef.current = false
    const id = requestAnimationFrame(() => fitGraphToView())
    return () => cancelAnimationFrame(id)
  }, [showRelatedCves, entityType, edgeClassesKey, isolate, fitGraphToView, visible.nodes.length])

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
  const hasLoadMoreCursor = Boolean(
    graph.cursorsByNodeId && Object.values(graph.cursorsByNodeId).some(Boolean),
  )
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

      {graph.nodes.length > 0 && (
        <div className="investigate-chrome">
          <div className="investigate-chrome-checks">
            <Checkbox
              checked={showRelatedCves}
              onCheckedChange={(v) => setShowRelatedCves(v === true)}
              label={`Related CVEs (${relatedCveCount(graph)})`}
            />
            <Checkbox
              checked={isolate}
              onCheckedChange={(v) => setIsolate(v === true)}
              label="Isolate"
            />
            <Checkbox
              checked={includeSemantic}
              onCheckedChange={(v) => {
                if (v === true) {
                  void enableSemantic()
                  return
                }
                setIncludeSemantic(false)
                setEdgeClasses((prev) => {
                  const next = new Set(prev)
                  next.delete('semantic')
                  return next
                })
              }}
              label="Semantic"
            />
          </div>
          <div className="investigate-type-tabs mono" role="tablist" aria-label="Entity type filter">
            {ENTITY_TYPE_CHIPS.map((type) => (
              <button
                key={type}
                type="button"
                role="tab"
                aria-selected={entityType === type}
                className={`investigate-type-tab${entityType === type ? ' active' : ''}`}
                onClick={() => setEntityType(type)}
              >
                {type.toUpperCase()}
              </button>
            ))}
          </div>
          <div className="investigate-edge-tabs mono" role="tablist" aria-label="Edge class filter">
            {EDGE_CLASS_CHIPS.map((cls) => (
              <button
                key={cls}
                type="button"
                role="tab"
                aria-selected={edgeClasses.has(cls)}
                className={[
                  'investigate-edge-tab',
                  edgeClasses.has(cls) ? 'active' : '',
                  cls === 'semantic' && !includeSemantic ? 'investigate-edge-tab--latent' : '',
                ].filter(Boolean).join(' ')}
                onClick={() => toggleEdgeClass(cls)}
              >
                {EDGE_CLASS_LABELS[cls] || cls}
              </button>
            ))}
          </div>
          <label className="investigate-find control-field">
            <span className="control-field-label">FIND</span>
            <input
              className="investigate-search mono"
              aria-label="Find in graph"
              value={findText}
              onChange={(e) => setFindText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key !== 'Enter') return
                const q = findText.trim().toLowerCase()
                const match = visible.nodes.find((n) =>
                  (n.label || n.entity_id || '').toLowerCase().includes(q))
                if (!match) return
                const pos = positions.find((p) => p.node_id === match.node_id)
                const el = canvasRef.current
                if (!pos || !el) return
                userMovedRef.current = true
                setView((v) => ({
                  ...v,
                  x: el.clientWidth / 2 - pos.x * v.scale,
                  y: el.clientHeight / 2 - pos.y * v.scale,
                }))
                setSelectedId(match.node_id)
              }}
              placeholder="Label or id…"
              autoComplete="off"
            />
          </label>
        </div>
      )}

      <p className="investigate-hint mono">
        Scroll to zoom · drag to pan · click to inspect · double-click to expand. Edges encode evidence class, not certainty.
      </p>

      {showHonesty && (
        <div className="investigate-honesty mono" role="status">
          {graph.capped
            ? `Canvas capped at ${INVESTIGATE_GRAPH_MAX_NODES} nodes / ${INVESTIGATE_GRAPH_MAX_EDGES} edges — expand a focused node instead of widening everything. `
            : ''}
          {graph.truncated
            ? `Truncated — more hops exist than this page returned.${hasLoadMoreCursor ? ' Use LOAD MORE on selected nodes.' : ''} `
            : ''}
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
                  {visible.edges.map((edge) => {
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
                  {positions.filter((node) => visibleNodeIds.has(node.node_id)).map((node) => {
                    const active = node.node_id === selectedId
                    const expanding = node.node_id === expandingId
                    const dimmed = Boolean(highlightedNodeIds) && !highlightedNodeIds.has(node.node_id)
                    const findMatch = Boolean(findLower)
                      && (node.label || node.entity_id || '').toLowerCase().includes(findLower)
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
                          findMatch ? 'investigate-node-match' : '',
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
                        aria-label={`${node.entity_type} ${node.label || node.entity_id || ''}`.trim()}
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
              {selectedIncidents.length > 0 && (
                <>
                  <h3 className="investigate-inspector-title mono">INCIDENT EDGES</h3>
                  <ul className="investigate-incidents">
                    {selectedIncidents.map((edge) => {
                      const neighborId = otherNodeId(edge, selected.node_id)
                      const neighbor = nodesById.get(neighborId)
                      return (
                        <li key={edge.edge_id} className="investigate-incident">
                          <button
                            type="button"
                            className="investigate-incident-neighbor mono"
                            onClick={() => setSelectedId(neighborId)}
                          >
                            {neighbor?.entity_id || neighborId}
                          </button>
                          <span className="investigate-incident-meta mono">
                            {edge.edge_class} · {edge.source_key}
                            {edge.confidence ? ` · confidence ${edge.confidence}` : ''}
                            {edge.observed_at ? ` · observed ${edge.observed_at}` : ''}
                            {edge.fetched_at ? ` · fetched ${edge.fetched_at}` : ''}
                          </span>
                        </li>
                      )
                    })}
                  </ul>
                </>
              )}
              <div className="investigate-inspector-actions">
                {canExpandEntityType(selected.entity_type) && (
                  <button
                    type="button"
                    className="investigate-search-btn mono"
                    onClick={() => expandNode(selected)}
                    disabled={expandingId === selected.node_id}
                  >
                    EXPAND
                  </button>
                )}
                {selected && graph.cursorsByNodeId?.[selected.node_id] && !graph.capped && (
                  <button
                    type="button"
                    className="investigate-search-btn mono"
                    onClick={() => expandNode(selected, {
                      cursor: graph.cursorsByNodeId[selected.node_id],
                    })}
                    disabled={expandingId === selected.node_id}
                  >
                    LOAD MORE
                  </button>
                )}
                {selected.entity_type === 'cve' && onOpenCve && (
                  <button type="button" className="investigate-ghost-btn mono" onClick={() => onOpenCve(selected.entity_id)}>
                    OPEN CVE
                  </button>
                )}
                {selected.entity_type === 'ioc' && investigation && (
                  <button
                    type="button"
                    className="investigate-ghost-btn mono"
                    onClick={() => {
                      const parsed = parseIocEntityId(selected.entity_id, selected.label)
                      investigation.pivotToIoc(parsed.value, null, parsed.type)
                    }}
                  >
                    LOOKUP LIVE
                  </button>
                )}
                {selected.entity_type === 'technique' && investigation && (
                  <button
                    type="button"
                    className="investigate-ghost-btn mono"
                    onClick={() => investigation.pivotToTechnique(selected.entity_id, selected.label)}
                  >
                    OPEN IN FORGE
                  </button>
                )}
                {selected.entity_type === 'campaign' && onOpenForgeCampaigns && (
                  <button type="button" className="investigate-ghost-btn mono" onClick={onOpenForgeCampaigns}>
                    OPEN CAMPAIGNS
                  </button>
                )}
                {selected.entity_type === 'publication' && onOpenAdvisories && (
                  <button type="button" className="investigate-ghost-btn mono" onClick={onOpenAdvisories}>
                    OPEN ADVISORIES
                  </button>
                )}
                {selected.entity_type === 'cve' && onWatchlistChange && (
                  <button
                    type="button"
                    className="investigate-ghost-btn mono"
                    onClick={() => onWatchlistChange(selected.entity_id, 'pin')}
                  >
                    {watchlist?.getState(selected.entity_id) === 'pin' ? 'UNPIN WATCHLIST' : 'PIN WATCHLIST'}
                  </button>
                )}
                {investigation && (
                  <button type="button" className="investigate-ghost-btn mono" onClick={() => pinNode(selected)}>
                    PIN THREAD
                  </button>
                )}
                {investigation && (
                  <button
                    type="button"
                    className="investigate-ghost-btn mono"
                    onClick={() => visible.nodes
                      .filter((n) => n.entity_type === 'cve')
                      .forEach((n) => investigation.ensureCveInThread(n.entity_id))}
                  >
                    PIN VISIBLE CVEs
                  </button>
                )}
                <button
                  type="button"
                  className="investigate-ghost-btn mono"
                  onClick={() => copyToClipboard(selected.entity_id)}
                >
                  COPY ID
                </button>
                <button
                  type="button"
                  className="investigate-ghost-btn mono"
                  onClick={() => copyToClipboard(
                    formatNeighborhoodMarkdown(
                      selected,
                      incidentEdges(graph, selected.node_id),
                      nodesById,
                    ),
                  )}
                >
                  COPY NEIGHBORHOOD
                </button>
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
