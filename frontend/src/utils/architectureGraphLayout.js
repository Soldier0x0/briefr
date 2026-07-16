export const COL_WIDTH = 320
export const ROW_HEIGHT = 40
export const NODE_W = 260
export const NODE_H = 26
export const CLUSTER_TOP = 56

export const CLUSTER_ORDER = ['api', 'scheduler', 'database']

/**
 * Deterministic grid layout for architecture graph nodes.
 * One column per cluster, rows in server-provided order.
 */
export function computeGraphLayout(graph) {
  if (!graph) return { positioned: [], byId: new Map(), clusters: [], viewWidth: 400, viewHeight: 300 }
  const byCluster = new Map()
  for (const node of graph.nodes) {
    const list = byCluster.get(node.cluster) || []
    list.push(node)
    byCluster.set(node.cluster, list)
  }
  const clusters = graph.clusters || []
  const clusterIds = clusters.length ? clusters.map(c => c.id) : CLUSTER_ORDER
  const positioned = []
  const byId = new Map()
  clusterIds.forEach((clusterId, ci) => {
    const nodes = byCluster.get(clusterId) || []
    nodes.forEach((node, ni) => {
      const x = ci * COL_WIDTH + 20
      const y = ni * ROW_HEIGHT + CLUSTER_TOP
      const positionedNode = { ...node, x, y }
      positioned.push(positionedNode)
      byId.set(node.id, positionedNode)
    })
  })
  const maxRows = clusters.length
    ? Math.max(...clusters.map(c => positioned.filter(n => n.cluster === c.id).length), 1)
    : 1
  const viewWidth = Math.max(clusters.length, 1) * COL_WIDTH + 40
  const viewHeight = maxRows * ROW_HEIGHT + CLUSTER_TOP + 40
  return { positioned, byId, clusters, viewWidth, viewHeight }
}
