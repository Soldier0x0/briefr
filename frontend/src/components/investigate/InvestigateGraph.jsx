import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchInvestigationRelationships, resolveInvestigation } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import AsyncState from '../ui/AsyncState.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import { useInvestigationOptional, INV_TYPES, INV_SOURCES } from '../../context/InvestigationContext.jsx'
import { emptyGraphState, mergeGraphPage } from '../../utils/investigateGraphMerge.js'
import { seedPositions, stepForce } from '../../utils/investigateForceLayout.js'
import './InvestigateGraph.css'

const EDGE_STROKE = {
  direct_fact: 'var(--text)',
  reported: 'var(--accent-primary, var(--c-accent))',
  derived: 'var(--text2)',
  analyst_assertion: 'var(--warning, #d4a017)',
  semantic: 'var(--text3)',
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

export default function InvestigateGraph({ onOpenCve, isActive = true }) {
  const investigation = useInvestigationOptional()
  const [query, setQuery] = useState('')
  const [graph, setGraph] = useState(emptyGraphState)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [emptyTitle, setEmptyTitle] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [positions, setPositions] = useState([])
  const [expandingId, setExpandingId] = useState(null)
  const canvasRef = useRef(null)
  const sizeRef = useRef({ width: 800, height: 560 })
  const positionsRef = useRef([])
  const graphRef = useRef(graph)
  graphRef.current = graph
  positionsRef.current = positions

  const selected = useMemo(
    () => graph.nodes.find((node) => node.node_id === selectedId) || null,
    [graph.nodes, selectedId],
  )

  const runSearch = useCallback(async (raw) => {
    const q = (raw || '').trim()
    if (!q) return
    setLoading(true)
    setError(null)
    setEmptyTitle('')
    try {
      const resolved = await resolveInvestigation(q)
      const root = resolved?.root
      if (!root?.entity_type || !root?.entity_id) {
        setGraph(emptyGraphState())
        setEmptyTitle('Could not resolve that query.')
        return
      }
      const page = await fetchInvestigationRelationships(root.entity_type, root.entity_id)
      const merged = mergeGraphPage(emptyGraphState(), page)
      setGraph(merged)
      setSelectedId(root.node_id)
    } catch (err) {
      if (err?.status === 404) {
        setGraph(emptyGraphState())
        setEmptyTitle('Unknown entity — BRIEFR has no local graph for that query.')
        setError(null)
        return
      }
      setError(err)
      notifyApiError(err)
    } finally {
      setLoading(false)
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
      if (page?.truncated) {
        setEmptyTitle('')
      }
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

  useEffect(() => {
    const el = canvasRef.current
    if (!el) return undefined
    const measure = () => {
      const width = Math.max(el.clientWidth, 320)
      const height = Math.max(el.clientHeight, 360)
      sizeRef.current = { width, height }
      const prior = new Map(positionsRef.current.map((node) => [node.node_id, node]))
      setPositions(seedPositions(graphRef.current.nodes, width, height, prior))
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
    const loop = () => {
      const { width, height } = sizeRef.current
      const stepped = stepForce(positionsRef.current, graphRef.current.edges, width, height)
      positionsRef.current = stepped
      ticks += 1
      setPositions(stepped)
      if (ticks < maxTicks) frame = requestAnimationFrame(loop)
    }
    frame = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(frame)
  }, [isActive, graph.nodes, graph.edges])

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

  return (
    <div className="investigate-page">
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
        One-hop graph over stored intel. Click a node to expand. Edges are evidence class, not layout truth.
      </p>

      {(graph.truncated || graph.source_status === 'degraded' || graph.knowledge_state === 'stale' || graph.knowledge_state === 'partial') && graph.nodes.length > 0 && (
        <div className="investigate-honesty mono" role="status">
          {graph.truncated ? 'Truncated — more hops exist than this page returned. Expand another node or raise the limit later. ' : ''}
          {graph.source_status === 'degraded' ? 'Source status degraded. ' : ''}
          {graph.knowledge_state === 'stale' ? 'Knowledge is stale. ' : ''}
          {graph.knowledge_state === 'partial' ? 'Partial neighborhood.' : ''}
        </div>
      )}

      <div className="investigate-stage">
        <div className="investigate-canvas" ref={canvasRef}>
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
                {graph.edges.map((edge) => {
                  const source = positions.find((node) => node.node_id === edge.source_node_id)
                  const target = positions.find((node) => node.node_id === edge.target_node_id)
                  if (!source || !target) return null
                  const dashed = edge.edge_class === 'semantic'
                  return (
                    <line
                      key={edge.edge_id}
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      stroke={EDGE_STROKE[edge.edge_class] || 'var(--text3)'}
                      strokeWidth={edge.edge_class === 'direct_fact' ? 2 : 1.25}
                      strokeDasharray={dashed ? '4 3' : undefined}
                      opacity={0.85}
                    />
                  )
                })}
                {positions.map((node) => {
                  const active = node.node_id === selectedId
                  const expanding = node.node_id === expandingId
                  return (
                    <g
                      key={node.node_id}
                      className="investigate-node"
                      onClick={() => expandNode(node)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          expandNode(node)
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      aria-label={`${node.entity_type} ${node.label}`}
                    >
                      <circle
                        cx={node.x}
                        cy={node.y}
                        r={active ? 11 : 8}
                        fill={active ? 'var(--accent-selected)' : 'var(--surface-raised, var(--bg2))'}
                        stroke={active ? 'var(--accent-selected)' : 'var(--border-active, var(--border2))'}
                        strokeWidth={expanding ? 3 : 1.5}
                      />
                      <text
                        x={node.x}
                        y={node.y + 22}
                        textAnchor="middle"
                        className="investigate-node-label"
                      >
                        {(node.label || node.entity_id || '').slice(0, 28)}
                      </text>
                    </g>
                  )
                })}
              </svg>
            )}
          </AsyncState>
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
