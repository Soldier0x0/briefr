import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import {
  createInvestigationCase,
  fetchInvestigationCase,
  fetchInvestigationCases,
  fetchInvestigationRelationships,
  resolveInvestigation,
  updateInvestigationCase,
} from '../../api.js'
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
  splitGraphLayers,
  visibleGraph,
} from '../../utils/investigateGraphFilters.js'
import {
  cameraActionForStructuralChange,
  structuralReasonForExpand,
} from '../../utils/investigateCameraPolicy.js'
import {
  clearInvestigateDraft,
  hasInvestigateDraft,
  loadInvestigateDraft,
  saveInvestigateDraft,
} from '../../utils/investigateDraftStorage.js'
import { createCameraController } from '../../utils/investigateCameraController.js'
import { createGraphEngine } from '../../utils/investigateGraphEngine.js'
import { createDragTracker } from '../../utils/investigateDragPolicy.js'
import {
  applyGraphDom,
  applyNodeScaleDom,
  applyWorldTransform,
  hitRadius,
  screenToWorld,
  shouldShowLabel,
} from '../../utils/investigateGraphDom.js'
import {
  emptyGraphState,
  INVESTIGATE_GRAPH_MAX_EDGES,
  INVESTIGATE_GRAPH_MAX_NODES,
  investigationRelationshipParams,
  mergeGraphPage,
} from '../../utils/investigateGraphMerge.js'
import {
  DEFAULT_VIEW,
  computePointCloudBounds,
  truncateNodeLabel,
} from '../../utils/architectureGraphView.js'
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

function stableCaseSnapshotSignature(snapshot) {
  return JSON.stringify({
    root_id: snapshot?.root_id ?? null,
    nodes: snapshot?.nodes ?? [],
    edges: snapshot?.edges ?? [],
    positions: snapshot?.positions ?? [],
    view: snapshot?.view ?? null,
    filters: snapshot?.filters ?? {},
  })
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
  initialCaseId = '',
  onQueryResolved,
  onCaseOpened,
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
  const viewRef = useRef({ ...DEFAULT_VIEW })
  const [structuralVersion, setStructuralVersion] = useState(0)
  const [liveStatus, setLiveStatus] = useState('')
  const structuralReasonRef = useRef('none')
  const topologyModeRef = useRef('none')
  const lastExpandParentRef = useRef(null)
  const flyToNeighborhoodRef = useRef(null)
  const flyToVisibleRef = useRef(null)
  const draftSaveTimerRef = useRef(null)
  const [focusedNodeId, setFocusedNodeId] = useState(null)
  const [mobilePane, setMobilePane] = useState('graph')
  const [filtersOpen, setFiltersOpen] = useState(true)
  const [draftBanner, setDraftBanner] = useState(false)
  const [activeCaseId, setActiveCaseId] = useState('')
  const [activeCaseTitle, setActiveCaseTitle] = useState('')
  const [caseSaveState, setCaseSaveState] = useState('saved')
  const [casesList, setCasesList] = useState([])
  const [casesMenuOpen, setCasesMenuOpen] = useState(false)
  const [casesLoading, setCasesLoading] = useState(false)
  const caseAutosaveTimerRef = useRef(null)
  const caseMenuRef = useRef(null)
  const lastSavedSnapshotRef = useRef('')
  const lastConsumedCaseIdRef = useRef('')
  const dragRef = useRef(null)
  const nodeDragRef = useRef(null)
  const draggingNodeIdRef = useRef(null)
  const panningRef = useRef(false)
  const canvasRef = useRef(null)
  const worldRef = useRef(null)
  const sizeRef = useRef({ width: 800, height: 560 })
  const positionsRef = useRef([])
  const graphRef = useRef(graph)
  const visibleRef = useRef({ nodes: [], edges: [] })
  const searchGenRef = useRef(0)
  const expandGenRef = useRef(0)
  const lastConsumedInitialQueryRef = useRef('')
  const skipDebounceRef = useRef(false)
  const cameraRef = useRef(null)
  const engineRef = useRef(null)
  const cameraRafRef = useRef(0)
  const selectedIdRef = useRef(null)
  const hoveredIdRef = useRef(null)
  const findLowerRef = useRef('')
  graphRef.current = graph
  selectedIdRef.current = selectedId
  hoveredIdRef.current = hoveredId

  if (!cameraRef.current) {
    cameraRef.current = createCameraController(DEFAULT_VIEW, {
      reducedMotion: prefersReducedMotion(),
    })
  }
  if (!engineRef.current) {
    engineRef.current = createGraphEngine({
      prefersReducedMotion: prefersReducedMotion(),
      onFrame: (pos) => {
        positionsRef.current = pos
        applyGraphDom(canvasRef.current, pos, visibleRef.current.edges)
      },
      onSettled: (pos) => {
        if (draggingNodeIdRef.current) return
        positionsRef.current = pos
        setPositions(pos)
        const action = cameraActionForStructuralChange(structuralReasonRef.current)
        if (action === 'fit_all') fitGraphToViewRef.current?.()
        else if (action === 'fit_visible') flyToVisibleRef.current?.()
        else if (action === 'fly_neighborhood') {
          flyToNeighborhoodRef.current?.(lastExpandParentRef.current)
        }
      },
    })
  }
  const structuralVersionRef = useRef(0)
  structuralVersionRef.current = structuralVersion
  const fitGraphToViewRef = useRef(null)

  const bumpStructure = useCallback((message, reason = 'filter') => {
    structuralReasonRef.current = reason
    topologyModeRef.current = reason
    setStructuralVersion((n) => n + 1)
    if (message) setLiveStatus(message)
  }, [])

  const syncCameraView = useCallback((next) => {
    viewRef.current = next
    applyWorldTransform(worldRef.current, next)
    applyNodeScaleDom(canvasRef.current, next.scale, {
      selectedId: selectedIdRef.current,
      hoveredId: hoveredIdRef.current,
      findLower: findLowerRef.current,
      rootId: graphRef.current.root_id,
    })
  }, [])

  const startCameraLoop = useCallback(() => {
    if (cameraRafRef.current) return
    let last = performance.now()
    const loop = (now) => {
      const dt = now - last
      last = now
      const cam = cameraRef.current
      const display = cam.tick(dt)
      viewRef.current = display
      applyWorldTransform(worldRef.current, display)
      applyNodeScaleDom(canvasRef.current, display.scale, {
        selectedId: selectedIdRef.current,
        hoveredId: hoveredIdRef.current,
        findLower: findLowerRef.current,
        rootId: graphRef.current.root_id,
      })
      if (cam.isAnimating()) {
        cameraRafRef.current = requestAnimationFrame(loop)
      } else {
        cameraRafRef.current = 0
      }
    }
    cameraRafRef.current = requestAnimationFrame(loop)
  }, [])

  const stopCameraLoop = useCallback(() => {
    if (cameraRafRef.current && typeof cancelAnimationFrame === 'function') {
      cancelAnimationFrame(cameraRafRef.current)
      cameraRafRef.current = 0
    }
  }, [])

  useEffect(() => {
    return () => {
      if (cameraRafRef.current && typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(cameraRafRef.current)
        cameraRafRef.current = 0
      }
    }
  }, [])

  const fitGraphToView = useCallback(() => {
    const el = canvasRef.current
    const pos = positionsRef.current
    if (!el || !pos.length) return
    const bounds = computePointCloudBounds(pos, 12, 48)
    cameraRef.current.flyToBounds(bounds, el.clientWidth, el.clientHeight)
    startCameraLoop()
  }, [startCameraLoop])
  fitGraphToViewRef.current = fitGraphToView

  const flyToNeighborhood = useCallback((parentId) => {
    if (!parentId) return
    const el = canvasRef.current
    if (!el) return
    const ids = new Set([parentId, ...neighborIds(graphRef.current, parentId)])
    const subset = positionsRef.current.filter((node) => ids.has(node.node_id))
    if (!subset.length) return
    const bounds = computePointCloudBounds(subset, 28, 80)
    cameraRef.current.flyToBounds(bounds, el.clientWidth, el.clientHeight)
    startCameraLoop()
  }, [startCameraLoop])
  flyToNeighborhoodRef.current = flyToNeighborhood

  const flyToVisible = useCallback(() => {
    const el = canvasRef.current
    if (!el) return
    const visibleIds = new Set(visibleRef.current.nodes.map((node) => node.node_id))
    const subset = positionsRef.current.filter((node) => visibleIds.has(node.node_id))
    if (!subset.length) return
    const bounds = computePointCloudBounds(subset, 12, 48)
    cameraRef.current.flyToBounds(bounds, el.clientWidth, el.clientHeight)
    startCameraLoop()
  }, [startCameraLoop])
  flyToVisibleRef.current = flyToVisible

  const buildCaseSnapshot = useCallback(() => ({
    root_id: graph.root_id,
    nodes: graph.nodes,
    edges: graph.edges,
    positions: positionsRef.current.map((node) => ({
      node_id: node.node_id,
      x: node.x,
      y: node.y,
    })),
    view: { ...viewRef.current },
    filters: {
      showRelatedCves,
      entityType,
      edgeClasses: [...edgeClasses],
      isolate,
      includeSemantic,
    },
  }), [graph, showRelatedCves, entityType, edgeClasses, isolate, includeSemantic])

  const hydrateFromSnapshot = useCallback((snapshot, title = '') => {
    if (!snapshot) return
    clearInvestigateDraft()
    setDraftBanner(false)
    setGraph({
      ...emptyGraphState(),
      nodes: snapshot.nodes || [],
      edges: snapshot.edges || [],
      root_id: snapshot.root_id || null,
    })
    if (snapshot.filters?.showRelatedCves != null) {
      setShowRelatedCves(snapshot.filters.showRelatedCves)
    }
    if (snapshot.filters?.entityType) setEntityType(snapshot.filters.entityType)
    if (snapshot.filters?.edgeClasses) {
      setEdgeClasses(new Set(snapshot.filters.edgeClasses))
    }
    if (snapshot.filters?.isolate != null) setIsolate(snapshot.filters.isolate)
    setIncludeSemantic(Boolean(snapshot.filters?.includeSemantic))
    if (!snapshot.filters?.includeSemantic) {
      setEdgeClasses((prev) => {
        const next = new Set(prev)
        next.delete('semantic')
        return next
      })
    }
    if (snapshot.view) {
      viewRef.current = { ...snapshot.view }
      cameraRef.current.setTargetView(snapshot.view, { immediate: prefersReducedMotion() })
      syncCameraView(snapshot.view)
    }
    if (snapshot.positions?.length) {
      positionsRef.current = snapshot.positions.map((node) => ({
        ...node,
        vx: 0,
        vy: 0,
      }))
      setPositions(positionsRef.current)
    }
    if (title) setActiveCaseTitle(title)
    structuralReasonRef.current = 'resolve'
    topologyModeRef.current = 'restore'
    lastExpandParentRef.current = null
    setSelectedId(snapshot.root_id)
    setStructuralVersion((n) => n + 1)
    setLiveStatus(title ? `Opened case ${title}.` : 'Opened saved case.')
  }, [syncCameraView])

  const markCaseDirty = useCallback(() => {
    if (!activeCaseId) return
    const next = stableCaseSnapshotSignature(buildCaseSnapshot())
    if (next !== lastSavedSnapshotRef.current) {
      setCaseSaveState('unsaved')
    }
  }, [activeCaseId, buildCaseSnapshot])

  const persistCase = useCallback(async (titleOverride = null) => {
    if (!graph.nodes.length) return null
    const snapshot = buildCaseSnapshot()
    setCaseSaveState('saving')
    try {
      if (activeCaseId) {
        const updated = await updateInvestigationCase(
          activeCaseId,
          snapshot,
          titleOverride || undefined,
        )
        setActiveCaseTitle(updated.title || activeCaseTitle)
        lastSavedSnapshotRef.current = stableCaseSnapshotSignature(snapshot)
        setCaseSaveState('saved')
        return updated
      }
      const title = (titleOverride || window.prompt('Case title (optional)') || '').trim()
      const created = await createInvestigationCase(snapshot, title || null)
      setActiveCaseId(created.id)
      setActiveCaseTitle(created.title || '')
      lastSavedSnapshotRef.current = stableCaseSnapshotSignature(snapshot)
      setCaseSaveState('saved')
      onCaseOpened?.(created.id)
      setLiveStatus(`Saved case ${created.title || created.id}.`)
      return created
    } catch (err) {
      setCaseSaveState('unsaved')
      notifyApiError(err)
      return null
    }
  }, [activeCaseId, activeCaseTitle, buildCaseSnapshot, graph.nodes.length, onCaseOpened])

  const openSavedCase = useCallback(async (caseId) => {
    if (!caseId) return
    setLoading(true)
    setError(null)
    try {
      const caseRow = await fetchInvestigationCase(caseId)
      hydrateFromSnapshot(caseRow.snapshot, caseRow.title)
      setActiveCaseId(caseRow.id)
      setActiveCaseTitle(caseRow.title || '')
      lastSavedSnapshotRef.current = stableCaseSnapshotSignature(caseRow.snapshot)
      setCaseSaveState('saved')
      onCaseOpened?.(caseRow.id)
      setCasesMenuOpen(false)
    } catch (err) {
      setError(err)
      notifyApiError(err)
    } finally {
      setLoading(false)
    }
  }, [hydrateFromSnapshot, onCaseOpened])

  const loadCasesList = useCallback(async () => {
    setCasesLoading(true)
    try {
      const body = await fetchInvestigationCases()
      setCasesList(body.cases || [])
    } catch (err) {
      notifyApiError(err)
    } finally {
      setCasesLoading(false)
    }
  }, [])

  useEffect(() => {
    const el = canvasRef.current
    if (!el) return undefined
    const handler = (e) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      cameraRef.current.zoomAtCursor(
        e.clientX - rect.left,
        e.clientY - rect.top,
        e.deltaY < 0 ? 1.1 : 1 / 1.1,
      )
      startCameraLoop()
    }
    el.addEventListener('wheel', handler, { passive: false })
    return () => el.removeEventListener('wheel', handler)
  }, [graph.root_id, startCameraLoop])

  const zoomFromButton = useCallback((factor) => {
    const el = canvasRef.current
    if (!el) return
    cameraRef.current.zoomAtCursor(el.clientWidth / 2, el.clientHeight / 2, factor)
    startCameraLoop()
  }, [startCameraLoop])

  const onPointerDown = useCallback((e) => {
    const nodeEl = e.target.closest('[data-node-id]')
    if (nodeEl) {
      const nodeId = nodeEl.getAttribute('data-node-id')
      const tracker = createDragTracker(4)
      tracker.start(e.clientX, e.clientY)
      nodeDragRef.current = { tracker, nodeId, pointerId: e.pointerId }
      e.currentTarget.setPointerCapture(e.pointerId)
      return
    }
    if (e.target.closest('button, input, a, [role="tab"], .investigate-camera-tools, .ui-checkbox, label')) return
    stopCameraLoop()
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      panOrigin: null,
      lastX: e.clientX,
      lastY: e.clientY,
      vx: 0,
      vy: 0,
      panning: false,
    }
    e.currentTarget.setPointerCapture(e.pointerId)
  }, [stopCameraLoop])

  const onPointerMove = useCallback((e) => {
    if (nodeDragRef.current) {
      const { tracker, nodeId } = nodeDragRef.current
      const mode = tracker.move(e.clientX, e.clientY)
      if (mode === 'drag') {
        draggingNodeIdRef.current = nodeId
        const rect = canvasRef.current.getBoundingClientRect()
        const world = screenToWorld(
          cameraRef.current.getDisplayView(),
          e.clientX - rect.left,
          e.clientY - rect.top,
        )
        engineRef.current.pinNode(nodeId, world.x, world.y)
      }
      return
    }
    if (!dragRef.current) return
    const { startX, startY } = dragRef.current
    const frameDx = e.clientX - dragRef.current.lastX
    const frameDy = e.clientY - dragRef.current.lastY
    dragRef.current.vx = frameDx
    dragRef.current.vy = frameDy
    dragRef.current.lastX = e.clientX
    dragRef.current.lastY = e.clientY
    if (!dragRef.current.panning) {
      if (Math.hypot(e.clientX - startX, e.clientY - startY) < 4) return
      dragRef.current.panning = true
      panningRef.current = true
      stopCameraLoop()
      dragRef.current.panOrigin = cameraRef.current.syncDisplayToTarget()
      dragRef.current.startX = e.clientX
      dragRef.current.startY = e.clientY
    }
    const dx = e.clientX - dragRef.current.startX
    const dy = e.clientY - dragRef.current.startY
    cameraRef.current.applyPanDelta(dragRef.current.panOrigin, dx, dy)
    syncCameraView(cameraRef.current.getDisplayView())
  }, [stopCameraLoop, syncCameraView])

  const onPointerUp = useCallback((e) => {
    if (nodeDragRef.current) {
      const { tracker, nodeId } = nodeDragRef.current
      const result = tracker.end()
      if (result === 'drag') {
        const dragged = engineRef.current.getPositions()
        positionsRef.current = dragged
        setPositions(dragged)
        draggingNodeIdRef.current = null
      } else if (result === 'click') {
        const node = graphRef.current.nodes.find((n) => n.node_id === nodeId)
        if (node) {
          setSelectedId((id) => (id === node.node_id ? null : node.node_id))
          setFocusedNodeId(node.node_id)
        }
      }
      nodeDragRef.current = null
    }
    if (dragRef.current) {
      const { panning, vx, vy } = dragRef.current
      panningRef.current = false
      if (panning) {
        cameraRef.current.nudgePanVelocity(vx, vy)
        startCameraLoop()
        syncCameraView(cameraRef.current.getDisplayView())
      } else if (!e.target.closest('[data-node-id]')) {
        setSelectedId(null)
      }
    }
    dragRef.current = null
    if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
  }, [startCameraLoop, syncCameraView])

  const onNodeClick = useCallback((node) => {
    setSelectedId((id) => (id === node.node_id ? null : node.node_id))
    setFocusedNodeId(node.node_id)
  }, [])

  const flyToNode = useCallback((nodeId) => {
    const pos = positionsRef.current.find((n) => n.node_id === nodeId)
    const el = canvasRef.current
    if (!pos || !el) return
    const bounds = computePointCloudBounds([pos], 28, 80)
    cameraRef.current.flyToBounds(bounds, el.clientWidth, el.clientHeight)
    startCameraLoop()
  }, [startCameraLoop])

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
      fitGraphToView()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setSelectedId(null)
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      const selected = graphRef.current.nodes.find((n) => n.node_id === (focusedNodeId || selectedId))
      if (selected) {
        e.preventDefault()
        const ids = [...neighborIds(graphRef.current, selected.node_id)]
        if (!ids.length) return
        const found = ids.indexOf(focusedNodeId)
        const backwards = e.key === 'ArrowLeft' || e.key === 'ArrowUp'
        const next = found < 0
          ? ids[backwards ? ids.length - 1 : 0]
          : ids[(found + (backwards ? -1 : 1) + ids.length) % ids.length]
        setFocusedNodeId(next)
        setSelectedId(next)
        flyToNode(next)
        return
      }
      e.preventDefault()
      const dx = e.key === 'ArrowLeft' ? 40 : e.key === 'ArrowRight' ? -40 : 0
      const dy = e.key === 'ArrowUp' ? 40 : e.key === 'ArrowDown' ? -40 : 0
      cameraRef.current.nudgePan(dx, dy)
      syncCameraView(cameraRef.current.getDisplayView())
    }
  }, [fitGraphToView, zoomFromButton, focusedNodeId, selectedId, flyToNode, syncCameraView])

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
      showSemantic: includeSemantic,
      entityType,
      edgeClasses,
      isolateNodeId: isolate ? (selectedId || graph.root_id) : null,
    }),
    [graph, showRelatedCves, includeSemantic, entityType, edgeClasses, isolate, selectedId],
  )
  visibleRef.current = visible

  const layers = useMemo(() => splitGraphLayers(graph), [graph])

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
    structuralReasonRef.current = 'resolve'
    topologyModeRef.current = 'resolve'
    lastExpandParentRef.current = null
    clearInvestigateDraft()
    setDraftBanner(false)
    setActiveCaseId('')
    setActiveCaseTitle('')
    setCaseSaveState('saved')
    lastSavedSnapshotRef.current = ''
    onCaseOpened?.('')
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
      bumpStructure(`Resolved ${root.entity_id}. ${merged.nodes.length} nodes.`, 'resolve')
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
  }, [onQueryResolved, bumpStructure, onCaseOpened])

  useEffect(() => {
    const q = (initialQuery || '').trim()
    if (!q || q === lastConsumedInitialQueryRef.current) return
    lastConsumedInitialQueryRef.current = q
    skipDebounceRef.current = true
    setQuery(q)
    runSearch(q)
  }, [initialQuery, runSearch])

  useEffect(() => {
    if ((initialQuery || '').trim()) return
    if ((initialCaseId || '').trim()) return
    if (graph.nodes.length > 0) return
    if (hasInvestigateDraft()) setDraftBanner(true)
  }, [initialQuery, initialCaseId, graph.nodes.length])

  useEffect(() => {
    const caseId = (initialCaseId || '').trim()
    if (!caseId || caseId === lastConsumedCaseIdRef.current) return
    lastConsumedCaseIdRef.current = caseId
    void openSavedCase(caseId)
  }, [initialCaseId, openSavedCase])

  useEffect(() => {
    markCaseDirty()
  }, [graph, positions, showRelatedCves, entityType, edgeClassesKey, isolate, includeSemantic, markCaseDirty])

  useEffect(() => {
    if (!casesMenuOpen) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setCasesMenuOpen(false)
    }
    const onPointerDown = (event) => {
      if (caseMenuRef.current?.contains(event.target)) return
      setCasesMenuOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [casesMenuOpen])

  useEffect(() => {
    if (!activeCaseId || caseSaveState !== 'unsaved') return undefined
    if (caseAutosaveTimerRef.current) clearTimeout(caseAutosaveTimerRef.current)
    caseAutosaveTimerRef.current = setTimeout(() => {
      void persistCase()
    }, 30000)
    return () => {
      if (caseAutosaveTimerRef.current) clearTimeout(caseAutosaveTimerRef.current)
    }
  }, [activeCaseId, caseSaveState, persistCase])

  useEffect(() => {
    if (!graph.nodes.length) return undefined
    if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current)
    draftSaveTimerRef.current = setTimeout(() => {
      saveInvestigateDraft({
        query,
        graph,
        positions: positionsRef.current.map((node) => ({
          node_id: node.node_id,
          x: node.x,
          y: node.y,
        })),
        view: viewRef.current,
        filters: {
          showRelatedCves,
          entityType,
          edgeClasses: [...edgeClasses],
          isolate,
          includeSemantic,
        },
      })
    }, 500)
    return () => {
      if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current)
    }
  }, [
    graph,
    query,
    showRelatedCves,
    entityType,
    edgeClassesKey,
    isolate,
    includeSemantic,
    positions,
  ])

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
    const expandReason = structuralReasonForExpand(params)
    structuralReasonRef.current = expandReason
    topologyModeRef.current = expandReason
    lastExpandParentRef.current = node.node_id
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
      const addedCount = (page.nodes || []).length
      setGraph((prev) => mergeGraphPage(prev, page))
      setSelectedId(node.node_id)
      if (addedCount === 0) {
        setLiveStatus(`No further stored hops for ${node.entity_id}.`)
      } else {
        bumpStructure(`Expanded ${node.entity_id} — added ${addedCount} nodes.`, expandReason)
      }
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
  }, [includeSemantic, bumpStructure])

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
  findLowerRef.current = findLower
  const findMatches = useMemo(() => {
    if (!findLower) return []
    return visible.nodes
      .filter((n) => (n.label || n.entity_id || '').toLowerCase().includes(findLower))
      .slice(0, 20)
  }, [visible.nodes, findLower])
  const heuristicIds = useMemo(() => heuristicCveIds(graph), [graph])
  const highlightedNodeIds = useMemo(() => {
    if (!focusId) return null
    const ids = new Set(neighborIds(graph, focusId))
    ids.add(focusId)
    if (graph.root_id) ids.add(graph.root_id)
    return ids
  }, [focusId, graph])

  useEffect(() => {
    if (!graph.nodes.length) return
    structuralReasonRef.current = 'filter'
    topologyModeRef.current = 'filter'
    setStructuralVersion((n) => n + 1)
  }, [showRelatedCves, entityType, edgeClassesKey, isolate])

  useEffect(() => {
    if (!graph.nodes.length) return
    const parts = [
      showRelatedCves
        ? `${layers.counts.relatedCves} related CVEs shown`
        : `${layers.counts.relatedCves} related CVEs hidden`,
    ]
    if (entityType !== 'all') parts.push(`${entityType} filter active`)
    if (isolate) parts.push('isolate mode')
    if (edgeClasses.size < EDGE_CLASS_CHIPS.length) {
      parts.push(`edge classes: ${[...edgeClasses].sort().join(', ')}`)
    }
    setLiveStatus(parts.join('; '))
  }, [
    showRelatedCves,
    entityType,
    edgeClassesKey,
    isolate,
    layers.counts.relatedCves,
    graph.nodes.length,
    edgeClasses,
  ])

  useEffect(() => {
    const el = canvasRef.current
    if (!el) return undefined
    const measure = () => {
      const width = Math.max(el.clientWidth, 320)
      const height = Math.max(el.clientHeight, 360)
      sizeRef.current = { width, height }
      engineRef.current.setSize(width, height)
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useLayoutEffect(() => {
    if (!graph.nodes.length || !positionsRef.current.length) return
    syncCameraView(viewRef.current)
    applyGraphDom(canvasRef.current, positionsRef.current, visibleRef.current.edges)
  })

  useLayoutEffect(() => {
    if (!isActive || visible.nodes.length === 0) return undefined
    const engine = engineRef.current
    engine.setSize(sizeRef.current.width, sizeRef.current.height)
    const mode = topologyModeRef.current
    const parentId = lastExpandParentRef.current
    if (mode === 'restore' && positionsRef.current.length) {
      engine.restorePositions(
        visible.nodes,
        visible.edges,
        graph.root_id,
        positionsRef.current,
      )
    } else if ((mode === 'expand' || mode === 'load_more') && parentId) {
      const parentPos = positionsRef.current.find((node) => node.node_id === parentId)
      if (parentPos) {
        engine.mergeTopology(visible.nodes, visible.edges, graph.root_id, {
          expandParentId: parentId,
          parentPosition: { x: parentPos.x, y: parentPos.y },
        })
      } else {
        engine.setTopology(visible.nodes, visible.edges, graph.root_id)
      }
    } else {
      engine.setTopology(visible.nodes, visible.edges, graph.root_id)
    }
    const seeded = engine.getPositions()
    positionsRef.current = seeded
    setPositions(seeded)
    applyGraphDom(canvasRef.current, seeded, visible.edges)
    syncCameraView(viewRef.current)
    engine.start()
    return () => engine.stop()
  }, [isActive, visible, graph.root_id, structuralVersion])

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
      {draftBanner && graph.nodes.length === 0 && (
        <div className="investigate-honesty investigate-draft-banner mono" role="status">
          Previous graph available.
          {' '}
          <button
            type="button"
            className="investigate-ghost-btn mono"
            onClick={() => {
              const draft = loadInvestigateDraft()
              if (!draft) {
                setDraftBanner(false)
                return
              }
              setQuery(draft.query || '')
              setGraph(draft.graph || emptyGraphState())
              if (draft.filters?.showRelatedCves != null) {
                setShowRelatedCves(draft.filters.showRelatedCves)
              }
              if (draft.filters?.entityType) setEntityType(draft.filters.entityType)
              if (draft.filters?.edgeClasses) {
                setEdgeClasses(new Set(draft.filters.edgeClasses))
              }
              if (draft.filters?.isolate != null) setIsolate(draft.filters.isolate)
              if (draft.filters?.includeSemantic) setIncludeSemantic(true)
              if (draft.view) {
                viewRef.current = { ...draft.view }
                cameraRef.current.setTargetView(draft.view, { immediate: true })
                syncCameraView(draft.view)
              }
              if (draft.positions?.length) {
                positionsRef.current = draft.positions.map((node) => ({
                  ...node,
                  vx: 0,
                  vy: 0,
                }))
                setPositions(positionsRef.current)
              }
              structuralReasonRef.current = 'resolve'
              topologyModeRef.current = 'resolve'
              setStructuralVersion((n) => n + 1)
              setDraftBanner(false)
              setLiveStatus('Restored previous graph draft.')
            }}
          >
            RESTORE
          </button>
          <button
            type="button"
            className="investigate-ghost-btn mono"
            onClick={() => {
              clearInvestigateDraft()
              setDraftBanner(false)
            }}
          >
            DISMISS
          </button>
        </div>
      )}

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
        {graph.nodes.length > 0 && (
          <>
            <button
              type="button"
              className="investigate-search-btn mono"
              disabled={caseSaveState === 'saving'}
              onClick={() => { void persistCase() }}
            >
              {caseSaveState === 'saving' ? 'SAVING…' : 'SAVE CASE'}
            </button>
            <div className="investigate-case-open" ref={caseMenuRef}>
              <button
                type="button"
                className="investigate-ghost-btn mono"
                aria-expanded={casesMenuOpen}
                aria-haspopup="menu"
                onClick={() => {
                  const next = !casesMenuOpen
                  setCasesMenuOpen(next)
                  if (next) void loadCasesList()
                }}
              >
                OPEN
              </button>
              {casesMenuOpen && (
                <div className="investigate-case-menu mono" role="menu">
                  {casesLoading && <div className="investigate-case-menu-empty">Loading…</div>}
                  {!casesLoading && casesList.length === 0 && (
                    <div className="investigate-case-menu-empty">No saved cases</div>
                  )}
                  {!casesLoading && casesList.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      role="menuitem"
                      className="investigate-case-menu-item"
                      onClick={() => { void openSavedCase(item.id) }}
                    >
                      {item.title || item.root_node_id}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </form>

      {activeCaseId && (
        <div className="investigate-honesty investigate-case-banner mono" role="status">
          Case: {activeCaseTitle || activeCaseId}
          {' · '}
          {caseSaveState === 'saving' ? 'Saving…' : caseSaveState === 'unsaved' ? 'Unsaved changes' : 'Saved'}
        </div>
      )}

      {graph.nodes.length > 0 && (
        <div className="investigate-chrome">
          <div className="investigate-mobile-tabs" role="tablist" aria-label="Investigate panes">
            <button
              type="button"
              role="tab"
              aria-selected={mobilePane === 'graph'}
              className={`investigate-type-tab${mobilePane === 'graph' ? ' active' : ''}`}
              onClick={() => setMobilePane('graph')}
            >
              GRAPH
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mobilePane === 'inspector'}
              className={`investigate-type-tab${mobilePane === 'inspector' ? ' active' : ''}`}
              onClick={() => setMobilePane('inspector')}
            >
              INSPECTOR
            </button>
          </div>
          <button
            type="button"
            className="investigate-filters-toggle investigate-ghost-btn mono"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
          >
            {filtersOpen ? 'HIDE FILTERS' : 'FILTERS'}
          </button>
          <div className={`investigate-chrome-body${filtersOpen ? '' : ' is-collapsed'}`}>
            <div className="investigate-chrome-checks">
            <Checkbox
              checked={showRelatedCves}
              onCheckedChange={(v) => setShowRelatedCves(v === true)}
              label={`Related CVEs (${layers.counts.relatedCves})`}
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
                const match = findMatches[0]
                if (!match) {
                  setLiveStatus('No matching nodes')
                  return
                }
                setSelectedId(match.node_id)
                setFocusedNodeId(match.node_id)
                flyToNode(match.node_id)
                setLiveStatus(`Found ${findMatches.length} match${findMatches.length === 1 ? '' : 'es'}`)
              }}
              placeholder="Label or id…"
              autoComplete="off"
            />
          </label>
          </div>
        </div>
      )}

      <p className="investigate-hint mono">
        Scroll to zoom · drag to pan · drag a node to rearrange · click to inspect · double-click to expand.
      </p>
      <div className="investigate-live" aria-live="polite">{liveStatus}</div>

      {!showRelatedCves && layers.counts.relatedCves > 0 && (
        <div className="investigate-honesty investigate-related-banner mono" role="status">
          {layers.counts.relatedCves} related CVEs available
          {' '}
          <button
            type="button"
            className="investigate-ghost-btn mono"
            onClick={() => setShowRelatedCves(true)}
          >
            Show related CVEs
          </button>
        </div>
      )}

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

      <div className={`investigate-stage investigate-stage--${mobilePane}`}>
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
                  id="investigate-world"
                  ref={worldRef}
                  className="investigate-svg-scene"
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
                        data-edge-id={edge.edge_id}
                        stroke={EDGE_STROKE[edge.edge_class] || 'var(--text-muted, var(--text3))'}
                        strokeWidth={edge.edge_class === 'direct_fact' ? 2 : 1.25}
                        strokeDasharray={dashed ? '4 3' : undefined}
                        opacity={edgeDimmed ? 0.2 : 0.85}
                      />
                    )
                  })}
                  {visible.nodes.map((node) => {
                    const nodePos = positionById.get(node.node_id)
                    if (!nodePos) return null
                    const active = node.node_id === selectedId
                    const expanding = node.node_id === expandingId
                    const dimmed = Boolean(highlightedNodeIds) && !highlightedNodeIds.has(node.node_id)
                    const findMatch = Boolean(findLower)
                      && (node.label || node.entity_id || '').toLowerCase().includes(findLower)
                    const liveScale = viewRef.current.scale
                    const showLabel = shouldShowLabel(node, {
                      selectedId,
                      hoveredId,
                      findLower,
                      scale: liveScale,
                      rootId: graph.root_id,
                    })
                    const dotR = nodeDotRadius(node, active, heuristicIds, graph.root_id)
                    const pinned = watchlist?.getState(node.entity_id) === 'pin'
                    const inThread = investigation?.isCveInThread?.(node.entity_id)
                    const hasMore = Boolean(graph.cursorsByNodeId?.[node.node_id]) && !graph.capped
                    return (
                      <g
                        key={node.node_id}
                        data-node-id={node.node_id}
                        data-entity-type={node.entity_type}
                        data-label={node.label || node.entity_id || ''}
                        className={[
                          'investigate-node',
                          dimmed ? 'investigate-node-dim' : '',
                          findMatch ? 'investigate-node-find-match investigate-node-match' : '',
                          node.node_id === focusedNodeId ? 'investigate-node-focused' : '',
                          expanding ? 'investigate-node-expanding' : '',
                        ].filter(Boolean).join(' ')}
                        onDoubleClick={() => onNodeDoubleClick(node)}
                        onMouseEnter={() => {
                          if (panningRef.current) return
                          setHoveredId(node.node_id)
                        }}
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
                        tabIndex={node.node_id === (focusedNodeId || selectedId || graph.root_id) ? 0 : -1}
                        role="button"
                        aria-pressed={active}
                        aria-label={`${node.entity_type} ${node.label || node.entity_id || ''}`.trim()}
                      >
                        <circle
                          className="investigate-node-hit"
                          cx={0}
                          cy={0}
                          r={hitRadius(liveScale)}
                        />
                        {inThread && (
                          <circle
                            className="investigate-node-thread"
                            cx={0}
                            cy={0}
                            r={dotR + 5}
                            fill="none"
                            stroke="var(--accent-primary, var(--c-accent))"
                            strokeWidth={1.25}
                            strokeDasharray="3 2"
                          />
                        )}
                        {renderNodeShape(node, 0, 0, active, expanding, heuristicIds, graph.root_id)}
                        {hasMore && (
                          <g
                            className="investigate-truncation-badge"
                            transform={`translate(${dotR + 6}, ${-dotR - 4})`}
                            onClick={(event) => {
                              event.stopPropagation()
                              expandNode(node, {
                                cursor: graph.cursorsByNodeId[node.node_id],
                              })
                            }}
                            onKeyDown={(event) => {
                              if (event.key !== 'Enter' && event.key !== ' ') return
                              event.preventDefault()
                              event.stopPropagation()
                              expandNode(node, {
                                cursor: graph.cursorsByNodeId[node.node_id],
                              })
                            }}
                            tabIndex={0}
                            role="button"
                            aria-label="More hops available — load more"
                          >
                            <circle r={10} className="investigate-truncation-badge-dot" />
                            <text textAnchor="middle" dy="0.35em" className="investigate-truncation-badge-label">+</text>
                          </g>
                        )}
                        {pinned && (
                          <polygon
                            className="investigate-node-pin"
                            points={`0,${-dotR - 6} -4,${-dotR - 2} 4,${-dotR - 2}`}
                            fill="none"
                            stroke="var(--accent-primary, var(--c-accent))"
                            strokeWidth={1.5}
                          />
                        )}
                        <text
                          x={0}
                          y={22}
                          textAnchor="middle"
                          className="investigate-node-label"
                          visibility={showLabel ? 'visible' : 'hidden'}
                        >
                          {truncateNodeLabel(node.label || node.entity_id || '', 28)}
                        </text>
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
                onClick={() => fitGraphToView()}
              >
                FIT GRAPH
              </button>
              <button
                type="button"
                aria-label="Reset view"
                onClick={() => fitGraphToView()}
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
                    {watchlist?.getState(selected.entity_id) === 'pin' ? 'UNWATCH' : 'WATCH'}
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
