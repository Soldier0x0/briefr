#!/usr/bin/env node
/**
 * Synthetic INVESTIGATE graph perf harness.
 * Run: node frontend/scripts/investigate-graph-perf.mjs
 */

import { performance } from 'node:perf_hooks'
import { createGraphEngine } from '../src/utils/investigateGraphEngine.js'

const NODE_COUNT = 200
const EDGE_COUNT = 300
const FRAMES = 60

function buildFixture() {
  const nodes = []
  const edges = []
  for (let i = 0; i < NODE_COUNT; i += 1) {
    nodes.push({
      node_id: `cve:CVE-2024-${String(i).padStart(4, '0')}`,
      entity_type: 'cve',
      entity_id: `CVE-2024-${String(i).padStart(4, '0')}`,
    })
  }
  const rootId = nodes[0].node_id
  for (let i = 0; i < EDGE_COUNT; i += 1) {
    const source = nodes[i % NODE_COUNT]
    const target = nodes[(i * 7 + 13) % NODE_COUNT]
    edges.push({
      edge_id: `edge-${i}`,
      source_node_id: source.node_id,
      target_node_id: target.node_id,
      edge_class: i % 5 === 0 ? 'semantic' : 'derived',
    })
  }
  return { nodes, edges, rootId }
}

function percentile(values, p) {
  const sorted = [...values].sort((a, b) => a - b)
  const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length))
  return sorted[idx]
}

const { nodes, edges, rootId } = buildFixture()
const engine = createGraphEngine({ prefersReducedMotion: true })
engine.setSize(1200, 800)
engine.setTopology(nodes, edges, rootId)

const frameMs = []
for (let frame = 0; frame < FRAMES; frame += 1) {
  const start = performance.now()
  while (engine.tick()) {
    // settle one simulation step per frame budget sample
    break
  }
  engine.getPositions()
  frameMs.push(performance.now() - start)
}

const p95 = percentile(frameMs, 95)
const budgetMs = 12
console.log(`investigate-graph-perf: nodes=${NODE_COUNT} edges=${EDGE_COUNT} frames=${FRAMES}`)
console.log(`p95 frame ms: ${p95.toFixed(2)} (budget ${budgetMs}ms)`)
if (p95 > budgetMs) {
  console.log('recommendation: enable canvas edge layer (VITE_INVESTIGATE_CANVAS_EDGES=1)')
  process.exitCode = 0
} else {
  console.log('recommendation: SVG path within budget; canvas layer optional')
}
